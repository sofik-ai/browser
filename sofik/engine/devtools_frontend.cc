// Copyright 2026 Sofik. All rights reserved.
// Portions copyright 2013 The Chromium Authors, under the BSD-style licence in
// //LICENSE.

#include "sofik/engine/devtools_frontend.h"

#include <optional>
#include <string_view>
#include <utility>

#include "base/base64.h"
#include "base/functional/bind.h"
#include "base/strings/string_number_conversions.h"
#include "base/strings/string_util.h"
#include "base/strings/utf_string_conversions.h"
#include "content/public/browser/devtools_agent_host.h"
#include "content/public/browser/devtools_frontend_host.h"
#include "content/public/browser/navigation_handle.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/storage_partition.h"
#include "content/public/browser/web_contents.h"
#include "headless/public/sofik_devtools.h"
#include "ipc/constants.mojom.h"
#include "net/base/net_errors.h"
#include "net/http/http_response_headers.h"
#include "net/traffic_annotation/network_traffic_annotation.h"
#include "services/network/public/cpp/resource_request.h"
#include "services/network/public/cpp/simple_url_loader.h"
#include "services/network/public/cpp/simple_url_loader_stream_consumer.h"
#include "services/network/public/mojom/url_response_head.mojom.h"
#include "url/gurl.h"

namespace sofik {
namespace {

// A protocol message larger than this goes to the front end in pieces.
constexpr size_t kMaxMessageChunkSize =
    IPC::mojom::kChannelMaximumMessageSize / 4;

base::DictValue ResponseFor(const net::HttpResponseHeaders* headers,
                            bool success,
                            int net_error) {
  base::DictValue response;
  response.Set("statusCode",
               headers ? headers->response_code() : (success ? 200 : 404));
  response.Set("netError", net_error);
  response.Set("netErrorName", net::ErrorToString(net_error));
  base::DictValue fields;
  size_t iterator = 0;
  std::string name;
  std::string value;
  while (headers && headers->EnumerateHeaderLines(&iterator, &name, &value)) {
    fields.Set(name, value);
  }
  response.Set("headers", std::move(fields));
  return response;
}

}  // namespace

// Fetches what the front end asks for -- source maps, mostly -- with the
// inspected page's own network context, and streams it back.
class DevToolsFrontend::ResourceLoader
    : public network::SimpleURLLoaderStreamConsumer {
 public:
  ResourceLoader(int stream_id,
                 int request_id,
                 DevToolsFrontend* frontend,
                 std::unique_ptr<network::SimpleURLLoader> loader,
                 network::mojom::URLLoaderFactory* factory)
      : stream_id_(stream_id),
        request_id_(request_id),
        frontend_(frontend),
        loader_(std::move(loader)) {
    loader_->SetOnResponseStartedCallback(base::BindOnce(
        &ResourceLoader::OnResponseStarted, base::Unretained(this)));
    loader_->DownloadAsStream(factory, this);
  }

 private:
  void OnResponseStarted(const GURL& final_url,
                         const network::mojom::URLResponseHead& head) {
    headers_ = head.headers;
  }

  // network::SimpleURLLoaderStreamConsumer:
  void OnDataReceived(std::string_view chunk,
                      base::OnceClosure resume) override {
    const bool encoded = !base::IsStringUTF8(chunk);
    frontend_->Call("streamWrite", base::Value(stream_id_),
                    encoded ? base::Value(base::Base64Encode(chunk))
                            : base::Value(chunk),
                    base::Value(encoded));
    std::move(resume).Run();
  }
  void OnComplete(bool success) override {
    frontend_->Ack(request_id_,
                   ResponseFor(headers_.get(), success, loader_->NetError()));
    frontend_->loaders_.erase(frontend_->loaders_.find(this));  // Deletes this.
  }
  void OnRetry(base::OnceClosure start_retry) override { NOTREACHED(); }

  const int stream_id_;
  const int request_id_;
  const raw_ptr<DevToolsFrontend> frontend_;
  std::unique_ptr<network::SimpleURLLoader> loader_;
  scoped_refptr<net::HttpResponseHeaders> headers_;
};

// static
std::string DevToolsFrontend::URL() {
  // targetType=tab: the front end attaches to the tab and follows the page
  // across the process swaps of cross-site navigations.
  return std::string(headless::kSofikDevToolsFrontendURL) + "?targetType=tab";
}

DevToolsFrontend::DevToolsFrontend(content::WebContents* frontend,
                                   content::WebContents* inspected,
                                   base::OnceClosure on_inspected_gone)
    : content::WebContentsObserver(frontend),
      inspected_(inspected),
      on_inspected_gone_(std::move(on_inspected_gone)) {}

DevToolsFrontend::~DevToolsFrontend() {
  if (agent_host_) {
    agent_host_->DetachClient(this);
  }
}

void DevToolsFrontend::ReadyToCommitNavigation(
    content::NavigationHandle* handle) {
  // The front end's page gets the DevToolsHost object it talks through. Only
  // its main frame, and only while it is the front end that is loading.
  if (handle->IsInPrimaryMainFrame() &&
      handle->GetURL().SchemeIs(headless::kSofikDevToolsScheme)) {
    frontend_host_ = content::DevToolsFrontendHost::Create(
        handle->GetRenderFrameHost(),
        base::BindRepeating(&DevToolsFrontend::HandleMessage,
                            base::Unretained(this)));
  }
}

void DevToolsFrontend::PrimaryMainDocumentElementAvailable() {
  if (agent_host_) {
    agent_host_->DetachClient(this);
    agent_host_ = nullptr;
  }
  if (!inspected_) {
    return;
  }
  agent_host_ = content::DevToolsAgentHost::GetOrCreateForTab(inspected_);
  agent_host_->AttachClient(this);
}

void DevToolsFrontend::WebContentsDestroyed() {
  if (agent_host_) {
    agent_host_->DetachClient(this);
    agent_host_ = nullptr;
  }
  frontend_host_.reset();
}

void DevToolsFrontend::HandleMessage(base::DictValue message) {
  const std::string* method = message.FindString("method");
  if (!method) {
    return;
  }
  const int request_id = message.FindInt("id").value_or(0);
  base::ListValue params;
  if (base::ListValue* given = message.FindList("params")) {
    params = std::move(*given);
  }

  if (*method == "dispatchProtocolMessage" && params.size() == 1) {
    const std::string* protocol_message = params[0].GetIfString();
    if (agent_host_ && protocol_message) {
      agent_host_->DispatchProtocolMessage(
          this, base::as_byte_span(*protocol_message));
    }
    return;
  }
  if (*method == "loadNetworkResource" && params.size() == 3) {
    const std::string* url = params[0].GetIfString();
    const std::string* headers = params[1].GetIfString();
    std::optional<int> stream_id = params[2].GetIfInt();
    if (url && headers && stream_id) {
      LoadNetworkResource(request_id, *url, *headers, *stream_id);
    }
    return;
  }
  if (*method == "getPreferences") {
    Ack(request_id, preferences_.Clone());
    return;
  }

  if (*method == "loadCompleted") {
    // Menus drawn by the front end itself: there is no native menu to show
    // from a view that may be a texture.
    Call("setUseSoftMenu", base::Value(true));
  } else if (*method == "setPreference" && params.size() >= 2) {
    const std::string* name = params[0].GetIfString();
    if (name && params[1].is_string()) {
      preferences_.Set(*name, std::move(params[1]));
    }
  } else if (*method == "removePreference" && !params.empty()) {
    if (const std::string* name = params[0].GetIfString()) {
      preferences_.Remove(*name);
    }
  } else if (*method == "clearPreferences") {
    preferences_.clear();
  } else if (*method == "requestFileSystems") {
    Call("fileSystemsLoaded", base::Value(base::Value::Type::LIST));
  } else if (*method == "reattach") {
    if (agent_host_) {
      agent_host_->DetachClient(this);
      agent_host_->AttachClient(this);
    }
  }
  // Everything else the front end may ask of an embedder -- open in a new
  // tab, save a file, bring to front -- has no meaning here, and is
  // acknowledged so that the front end does not wait on it.
  if (request_id) {
    Ack(request_id, {});
  }
}

void DevToolsFrontend::LoadNetworkResource(int request_id,
                                           const std::string& url,
                                           const std::string& headers,
                                           int stream_id) {
  GURL gurl(url);
  if (!gurl.is_valid() || !inspected_) {
    base::DictValue response;
    response.Set("statusCode", 404);
    response.Set("urlValid", false);
    Ack(request_id, std::move(response));
    return;
  }
  net::NetworkTrafficAnnotationTag annotation =
      net::DefineNetworkTrafficAnnotation("sofik_devtools_frontend", R"(
        semantics {
          sender: "Developer Tools"
          description:
            "With Developer Tools open, the browser fetches resources that "
            "help debugging, such as source maps."
          trigger: "The person opens Developer Tools on a page."
          data: "Whatever Developer Tools asks for."
          destination: OTHER
        }
        policy {
          cookies_allowed: YES
          cookies_store: "user"
          setting: "Only while Developer Tools is open."
          policy_exception_justification: "Not a Chrome feature."
        })");
  auto request = std::make_unique<network::ResourceRequest>();
  request->url = gurl;
  request->site_for_cookies = net::SiteForCookies::FromUrl(gurl);
  request->headers.AddHeadersFromString(headers);

  auto factory = inspected_->GetPrimaryMainFrame()
                     ->GetStoragePartition()
                     ->GetURLLoaderFactoryForBrowserProcess();
  loaders_.insert(std::make_unique<ResourceLoader>(
      stream_id, request_id, this,
      network::SimpleURLLoader::Create(std::move(request), annotation),
      factory.get()));
}

void DevToolsFrontend::Call(const std::string& method,
                            base::Value arg1,
                            base::Value arg2,
                            base::Value arg3) {
  if (!web_contents()) {
    return;
  }
  base::ListValue arguments;
  for (base::Value* arg : {&arg1, &arg2, &arg3}) {
    if (arg->is_none()) {
      break;
    }
    arguments.Append(std::move(*arg));
  }
  content::RenderFrameHost* frame = web_contents()->GetPrimaryMainFrame();
  // The content layer lets an embedder run script only in pages it declares
  // its own; the front end is one.
  frame->AllowInjectingJavaScript();
  frame->ExecuteJavaScriptMethod(u"DevToolsAPI", base::ASCIIToUTF16(method),
                                 std::move(arguments), base::DoNothing());
}

void DevToolsFrontend::Ack(int request_id, base::DictValue result) {
  Call("embedderMessageAck", base::Value(request_id),
       base::Value(std::move(result)));
}

void DevToolsFrontend::DispatchProtocolMessage(
    content::DevToolsAgentHost* host,
    base::span<const uint8_t> message) {
  std::string_view text = base::as_string_view(message);
  if (text.size() < kMaxMessageChunkSize) {
    Call("dispatchMessage", base::Value(text));
    return;
  }
  for (size_t pos = 0; pos < text.size(); pos += kMaxMessageChunkSize) {
    // The first chunk announces the total; the rest say 0.
    Call("dispatchMessageChunk",
         base::Value(text.substr(pos, kMaxMessageChunkSize)),
         base::Value(base::NumberToString(pos ? 0 : text.size())));
  }
}

void DevToolsFrontend::AgentHostClosed(content::DevToolsAgentHost* host) {
  agent_host_ = nullptr;
  inspected_ = nullptr;
  if (on_inspected_gone_) {
    std::move(on_inspected_gone_).Run();
  }
}

bool DevToolsFrontend::MayAccessAllCookies() {
  return true;
}

}  // namespace sofik
