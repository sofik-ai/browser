// Copyright 2026 Sofik. All rights reserved.

#include "components/sofik/identity.h"

#include <memory>

#include "base/environment.h"
#include "base/strings/cstring_view.h"
#include "base/logging.h"
#include "base/no_destructor.h"
#include "third_party/icu/source/i18n/unicode/timezone.h"

namespace sofik {
namespace {

// Read from the environment rather than from a switch, because the values have
// to be in place before the command line is parsed: ICU resolves its default
// zone during startup, and a timezone applied after that is already too late
// for the first page.
constexpr base::cstring_view kTimezoneVar = "SOFIK_BROWSER_TIMEZONE";
constexpr base::cstring_view kLocaleVar = "SOFIK_BROWSER_LOCALE";

// What Chrome reports. A Chromium build leaves this out of the brand list,
// which is the contradiction this exists to close.
constexpr char kChromeBrand[] = "Google Chrome";

std::string ReadVar(base::Environment* environment,
                    base::cstring_view name) {
  // A variable set to nothing counts as unset: an empty timezone would
  // otherwise reach ICU as a request for the zone named "".
  return environment->GetVar(name).value_or(std::string());
}

}  // namespace

Identity::Identity() {
  auto environment = base::Environment::Create();
  timezone_ = ReadVar(environment.get(), kTimezoneVar);
  locale_ = ReadVar(environment.get(), kLocaleVar);
  brand_ = kChromeBrand;
  is_spoofed_ = !timezone_.empty() || !locale_.empty();
}

// static
const Identity& Identity::Get() {
  static const base::NoDestructor<Identity> instance;
  return *instance;
}

void ApplyIdentityTimezone() {
  const std::string& zone = Identity::Get().timezone();
  if (zone.empty()) {
    return;
  }
  // createTimeZone answers the "unknown" zone for a name it does not have,
  // rather than failing. Adopting that would silently put the browser on UTC
  // with no relation to the address its traffic comes from -- worse than the
  // real zone, and invisible. Check first.
  std::unique_ptr<icu::TimeZone> requested(
      icu::TimeZone::createTimeZone(icu::UnicodeString::fromUTF8(zone)));
  if (!requested || *requested == icu::TimeZone::getUnknown()) {
    LOG(ERROR) << "sofik: unknown timezone '" << zone
               << "'; keeping the system zone";
    return;
  }
  // adoptDefault takes ownership.
  icu::TimeZone::adoptDefault(requested.release());
}

}  // namespace sofik
