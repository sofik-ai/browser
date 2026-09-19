// Copyright 2026 Sofik. All rights reserved.

#ifndef SOFIK_ENGINE_DOWNLOADS_H_
#define SOFIK_ENGINE_DOWNLOADS_H_

#include <map>

#include "base/memory/raw_ptr.h"
#include "components/download/public/common/download_item.h"
#include "components/download/public/common/download_target_info.h"
#include "content/public/browser/download_manager_delegate.h"
#include "sofik/engine/sofik_engine.h"

namespace sofik {

// Asks the host where each download goes.
//
// The page chooses the file name, so the engine never turns one into a path:
// it hands the name over as data and writes wherever the host says. A host
// that does not answer leaves the download pending; one with no callback
// declines it, which is also what happens to a download no view owns.
class Downloads : public content::DownloadManagerDelegate,
                  public download::DownloadItem::Observer {
 public:
  Downloads();
  Downloads(const Downloads&) = delete;
  Downloads& operator=(const Downloads&) = delete;
  ~Downloads() override;

  // The host's answer. An empty path declines.
  void Answer(uint32_t request, const std::string& path);

  // content::DownloadManagerDelegate:
  void GetNextId(content::DownloadIdCallback callback) override;
  bool DetermineDownloadTarget(
      download::DownloadItem* item,
      download::DownloadTargetCallback* callback) override;

  // download::DownloadItem::Observer:
  void OnDownloadUpdated(download::DownloadItem* item) override;
  void OnDownloadDestroyed(download::DownloadItem* item) override;

 private:
  struct Pending {
    Pending();
    Pending(Pending&&);
    ~Pending();
    raw_ptr<download::DownloadItem> item;
    download::DownloadTargetCallback callback;
  };

  std::map<uint32_t, Pending> pending_;
  // Which view each running download reports to.
  std::map<raw_ptr<download::DownloadItem>, sofik_view_id> owners_;
  uint32_t next_request_ = 1;
  uint32_t next_download_id_ = 1;
};

}  // namespace sofik

#endif  // SOFIK_ENGINE_DOWNLOADS_H_
