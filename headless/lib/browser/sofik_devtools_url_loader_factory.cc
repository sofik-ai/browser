// Copyright 2026 Sofik. All rights reserved.

#include "headless/lib/browser/sofik_devtools_url_loader_factory.h"

#include <memory>
#include <string>
#include <string_view>
#include <utility>

#include "base/functional/bind.h"
#include "base/memory/ref_counted_memory.h"
#include "base/strings/string_util.h"
#include "content/public/browser/devtools_frontend_host.h"
#include "headless/public/sofik_devtools.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "mojo/public/cpp/system/data_pipe.h"
#include "mojo/public/cpp/system/data_pipe_producer.h"
#include "mojo/public/cpp/system/string_data_source.h"
#include "net/base/net_errors.h"
#include "net/http/http_response_headers.h"
#include "services/network/public/cpp/resource_request.h"
#include "services/network/public/mojom/url_loader.mojom.h"
#include "services/network/public/mojom/url_response_head.mojom.h"
#include "url/gurl.h"

namespace headless {
namespace {

constexpr std::string_view kBundledPrefix = "/bundled/";

std::string_view MimeTypeFor(std::string_view path) {
  const auto ends_with = [&](std::string_view suffix) {
    return base::EndsWith(path, suffix, base::CompareCase::INSENSITIVE_ASCII);
  };
  if (ends_with(".html")) return "text/html";
  if (ends_with(".js") || ends_with(".mjs")) return "text/javascript";
  if (ends_with(".css")) return "text/css";
  if (ends_with(".json") || ends_with(".map")) return "application/json";
  if (ends_with(".svg")) return "image/svg+xml";
  if (ends_with(".png")) return "image/png";
  if (ends_with(".gif")) return "image/gif";
  if (ends_with(".avif")) return "image/avif";
  if (ends_with(".wasm")) return "application/wasm";
  if (ends_with(".woff2")) return "font/woff2";
  return "text/plain";
}

// Keeps the bytes alive for as long as the pipe is being fed.
struct Write {
  mojo::Remote<network::mojom::URLLoaderClient> client;
  scoped_refptr<base::RefCountedMemory> bytes;
  std::unique_ptr<mojo::DataPipeProducer> producer;
};

void OnWritten(std::unique_ptr<Write> write, MojoResult result) {
  if (result != MOJO_RESULT_OK) {
    write->client->OnComplete(
        network::URLLoaderCompletionStatus(net::ERR_FAILED));
    return;
  }
  network::URLLoaderCompletionStatus status(net::OK);
  status.encoded_data_length = write->bytes->size();
  status.encoded_body_length = write->bytes->size();
  status.decoded_body_length = write->bytes->size();
  write->client->OnComplete(status);
}

}  // namespace

// static
mojo::PendingRemote<network::mojom::URLLoaderFactory>
SofikDevToolsURLLoaderFactory::Create() {
  mojo::PendingRemote<network::mojom::URLLoaderFactory> remote;
  // Deletes itself when the last receiver goes away.
  new SofikDevToolsURLLoaderFactory(remote.InitWithNewPipeAndPassReceiver());
  return remote;
}

SofikDevToolsURLLoaderFactory::SofikDevToolsURLLoaderFactory(
    mojo::PendingReceiver<network::mojom::URLLoaderFactory> receiver)
    : network::SelfDeletingURLLoaderFactory(std::move(receiver)) {}

SofikDevToolsURLLoaderFactory::~SofikDevToolsURLLoaderFactory() = default;

void SofikDevToolsURLLoaderFactory::CreateLoaderAndStart(
    mojo::PendingReceiver<network::mojom::URLLoader> loader,
    int32_t request_id,
    uint32_t options,
    const network::ResourceRequest& request,
    mojo::PendingRemote<network::mojom::URLLoaderClient> client,
    const net::MutableNetworkTrafficAnnotationTag& traffic_annotation) {
  mojo::Remote<network::mojom::URLLoaderClient> client_remote(
      std::move(client));

  const GURL& url = request.url;
  scoped_refptr<base::RefCountedMemory> bytes;
  std::string path = url.GetPath();
  if (url.SchemeIs(kSofikDevToolsScheme) && url.GetHost() == kSofikDevToolsHost &&
      base::StartsWith(path, kBundledPrefix)) {
    path = path.substr(kBundledPrefix.size());
    bytes = content::DevToolsFrontendHost::GetFrontendResourceBytes(path);
  }
  if (!bytes) {
    client_remote->OnComplete(
        network::URLLoaderCompletionStatus(net::ERR_FILE_NOT_FOUND));
    return;
  }

  auto response = network::mojom::URLResponseHead::New();
  response->mime_type = std::string(MimeTypeFor(path));
  response->charset = "utf-8";
  response->headers = net::HttpResponseHeaders::TryToCreate(
      "HTTP/1.1 200 OK\r\nContent-Type: " + response->mime_type +
      "\r\nCache-Control: no-cache\r\n\r\n");
  response->content_length = bytes->size();

  mojo::ScopedDataPipeProducerHandle producer;
  mojo::ScopedDataPipeConsumerHandle consumer;
  if (mojo::CreateDataPipe(nullptr, producer, consumer) != MOJO_RESULT_OK) {
    client_remote->OnComplete(
        network::URLLoaderCompletionStatus(net::ERR_INSUFFICIENT_RESOURCES));
    return;
  }
  client_remote->OnReceiveResponse(std::move(response), std::move(consumer),
                                   std::nullopt);

  auto write = std::make_unique<Write>();
  write->client = std::move(client_remote);
  write->bytes = std::move(bytes);
  write->producer =
      std::make_unique<mojo::DataPipeProducer>(std::move(producer));
  mojo::DataPipeProducer* producer_ptr = write->producer.get();
  std::string_view body = base::as_string_view(*write->bytes);
  producer_ptr->Write(
      std::make_unique<mojo::StringDataSource>(
          body, mojo::StringDataSource::AsyncWritingMode::
                    STRING_STAYS_VALID_UNTIL_COMPLETION),
      base::BindOnce(&OnWritten, std::move(write)));
}

}  // namespace headless
