// Copyright 2026 Sofik. All rights reserved.

#ifndef HEADLESS_LIB_BROWSER_HEADLESS_NOTIFICATION_SERVICE_H_
#define HEADLESS_LIB_BROWSER_HEADLESS_NOTIFICATION_SERVICE_H_

#include <map>
#include <set>
#include <string>

#include "content/public/browser/platform_notification_service.h"
#include "url/gurl.h"

namespace headless {

// Sofik: notifications that are accepted and shown nowhere.
//
// A browser context with no notification service makes the content layer
// answer Notification.permission with "denied" while the Permissions API,
// which does not look at the service, answers "prompt" for the same thing.
// No real browser disagrees with itself like that, and the pair is one of the
// first things a bot check reads. With a service in place both follow the
// permission manager, and a page that is granted the permission can create
// notifications that behave: they show, they are listed, they close.
class HeadlessNotificationService : public content::PlatformNotificationService {
 public:
  HeadlessNotificationService();
  HeadlessNotificationService(const HeadlessNotificationService&) = delete;
  HeadlessNotificationService& operator=(const HeadlessNotificationService&) =
      delete;
  ~HeadlessNotificationService() override;

  // content::PlatformNotificationService:
  void DisplayNotification(
      const std::string& notification_id,
      const GURL& origin,
      const GURL& document_url,
      const blink::PlatformNotificationData& notification_data,
      const blink::NotificationResources& notification_resources) override;
  void DisplayPersistentNotification(
      const std::string& notification_id,
      const GURL& service_worker_origin,
      const GURL& origin,
      const blink::PlatformNotificationData& notification_data,
      const blink::NotificationResources& notification_resources) override;
  void CloseNotification(const std::string& notification_id) override;
  void ClosePersistentNotification(const std::string& notification_id) override;
  void GetDisplayedNotifications(
      DisplayedNotificationsCallback callback) override;
  void GetDisplayedNotificationsForOrigin(
      const GURL& origin,
      DisplayedNotificationsCallback callback) override;
  void ScheduleTrigger(base::Time timestamp) override {}
  base::Time ReadNextTriggerTimestamp() override;
  int64_t ReadNextPersistentNotificationId() override;
  void RecordNotificationUkmEvent(
      const content::NotificationDatabaseData& data) override {}

 private:
  std::map<std::string, GURL> displayed_;  // id -> origin
  int64_t next_persistent_id_ = 0;
};

}  // namespace headless

#endif  // HEADLESS_LIB_BROWSER_HEADLESS_NOTIFICATION_SERVICE_H_
