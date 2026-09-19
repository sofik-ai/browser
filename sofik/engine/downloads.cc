// Copyright 2026 Sofik. All rights reserved.

#include "sofik/engine/downloads.h"

#include <string>
#include <utility>

#include "base/files/file_path.h"
#include "base/strings/utf_string_conversions.h"
#include "components/download/public/common/download_interrupt_reasons.h"
#include "content/public/browser/download_item_utils.h"
#include "content/public/browser/web_contents.h"
#include "sofik/engine/engine.h"
#include "sofik/engine/view.h"

namespace sofik {
namespace {

// Strings have to stay alive for the length of the callback.
struct Described {
  std::string url, name, mime, path;
  sofik_download info = {};
};

void Describe(download::DownloadItem* item, Described& out) {
  out.url = item->GetURL().spec();
  out.name = item->GetSuggestedFilename();
  out.mime = item->GetMimeType();
  out.path = item->GetTargetFilePath().AsUTF8Unsafe();
  out.info.id = item->GetId();
  out.info.url = out.url.c_str();
  out.info.suggested_name = out.name.c_str();
  out.info.mime_type = out.mime.c_str();
  out.info.path = out.path.c_str();
  out.info.received_bytes = item->GetReceivedBytes();
  out.info.total_bytes = item->GetTotalBytes() > 0 ? item->GetTotalBytes() : -1;
  out.info.is_complete =
      item->GetState() == download::DownloadItem::COMPLETE;
  out.info.is_canceled =
      item->GetState() == download::DownloadItem::CANCELLED;
  out.info.is_interrupted =
      item->GetState() == download::DownloadItem::INTERRUPTED;
}

void Decline(download::DownloadTargetCallback callback) {
  download::DownloadTargetInfo target;
  target.interrupt_reason = download::DOWNLOAD_INTERRUPT_REASON_USER_CANCELED;
  std::move(callback).Run(std::move(target));
}

}  // namespace

Downloads::Pending::Pending() = default;
Downloads::Pending::Pending(Pending&&) = default;
Downloads::Pending::~Pending() = default;

Downloads::Downloads() = default;

Downloads::~Downloads() {
  for (auto& [item, view] : owners_) {
    item->RemoveObserver(this);
  }
}

void Downloads::GetNextId(content::DownloadIdCallback callback) {
  std::move(callback).Run(next_download_id_++);
}

bool Downloads::DetermineDownloadTarget(
    download::DownloadItem* item,
    download::DownloadTargetCallback* callback) {
  content::WebContents* web_contents =
      content::DownloadItemUtils::GetWebContents(item);
  View* view = Engine::Get() ? Engine::Get()->FindView(web_contents) : nullptr;
  if (!view || !view->callbacks().on_download_requested) {
    Decline(std::move(*callback));
    return true;
  }

  const uint32_t request = next_request_++;
  Pending pending;
  pending.item = item;
  pending.callback = std::move(*callback);
  pending_.emplace(request, std::move(pending));
  if (!owners_.contains(item)) {
    owners_[item] = view->id();
    item->AddObserver(this);
  }

  Described described;
  Describe(item, described);
  view->callbacks().on_download_requested(view->user(), view->id(), request,
                                          &described.info);
  return true;
}

void Downloads::Answer(uint32_t request, const std::string& path) {
  auto found = pending_.find(request);
  if (found == pending_.end()) {
    return;
  }
  Pending pending = std::move(found->second);
  pending_.erase(found);
  if (path.empty()) {
    Decline(std::move(pending.callback));
    return;
  }
  download::DownloadTargetInfo target;
  target.target_path = base::FilePath::FromUTF8Unsafe(path);
  // Written under another name until it is whole, so a half-written file is
  // never mistaken for the download.
  target.intermediate_path =
      target.target_path.AddExtensionASCII("sofikdownload");
  target.display_name = target.target_path.BaseName();
  target.mime_type = pending.item->GetMimeType();
  std::move(pending.callback).Run(std::move(target));
}

void Downloads::OnDownloadUpdated(download::DownloadItem* item) {
  auto owner = owners_.find(item);
  if (owner == owners_.end() || !Engine::Get()) {
    return;
  }
  View* view = Engine::Get()->FindView(owner->second);
  if (!view || !view->callbacks().on_download_updated) {
    return;
  }
  Described described;
  Describe(item, described);
  view->callbacks().on_download_updated(view->user(), view->id(),
                                        &described.info);
}

void Downloads::OnDownloadDestroyed(download::DownloadItem* item) {
  item->RemoveObserver(this);
  owners_.erase(item);
  std::erase_if(pending_, [item](const auto& entry) {
    return entry.second.item == item;
  });
}

}  // namespace sofik
