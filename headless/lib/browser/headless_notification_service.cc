// Copyright 2026 Sofik. All rights reserved.

#include "headless/lib/browser/headless_notification_service.h"

#include <utility>

#include "base/functional/callback_helpers.h"
#include "base/time/time.h"
#include "content/public/browser/notification_event_dispatcher.h"

namespace headless {

HeadlessNotificationService::HeadlessNotificationService() = default;
HeadlessNotificationService::~HeadlessNotificationService() = default;

void HeadlessNotificationService::DisplayNotification(
    const std::string& notification_id,
    const GURL& origin,
    const GURL& document_url,
    const blink::PlatformNotificationData& notification_data,
    const blink::NotificationResources& notification_resources) {
  displayed_[notification_id] = origin;
  // The page's onshow, which a real notification centre answers too.
  content::NotificationEventDispatcher::GetInstance()
      ->DispatchNonPersistentShowEvent(notification_id);
}

void HeadlessNotificationService::DisplayPersistentNotification(
    const std::string& notification_id,
    const GURL& service_worker_origin,
    const GURL& origin,
    const blink::PlatformNotificationData& notification_data,
    const blink::NotificationResources& notification_resources) {
  displayed_[notification_id] = origin;
}

void HeadlessNotificationService::CloseNotification(
    const std::string& notification_id) {
  if (displayed_.erase(notification_id)) {
    content::NotificationEventDispatcher::GetInstance()
        ->DispatchNonPersistentCloseEvent(notification_id, base::DoNothing());
  }
}

void HeadlessNotificationService::ClosePersistentNotification(
    const std::string& notification_id) {
  displayed_.erase(notification_id);
}

void HeadlessNotificationService::GetDisplayedNotifications(
    DisplayedNotificationsCallback callback) {
  std::set<std::string> ids;
  for (const auto& [id, origin] : displayed_) {
    ids.insert(id);
  }
  std::move(callback).Run(std::move(ids), /*supports_synchronization=*/true);
}

void HeadlessNotificationService::GetDisplayedNotificationsForOrigin(
    const GURL& origin,
    DisplayedNotificationsCallback callback) {
  std::set<std::string> ids;
  for (const auto& [id, displayed_origin] : displayed_) {
    if (displayed_origin == origin) {
      ids.insert(id);
    }
  }
  std::move(callback).Run(std::move(ids), /*supports_synchronization=*/true);
}

base::Time HeadlessNotificationService::ReadNextTriggerTimestamp() {
  return base::Time::Max();
}

int64_t HeadlessNotificationService::ReadNextPersistentNotificationId() {
  return ++next_persistent_id_;
}

}  // namespace headless
