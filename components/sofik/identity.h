// Copyright 2026 Sofik. All rights reserved.

#ifndef COMPONENTS_SOFIK_IDENTITY_H_
#define COMPONENTS_SOFIK_IDENTITY_H_

#include <string>

#include "base/no_destructor.h"

namespace sofik {

// The machine this browser claims to be.
//
// Every value a page can read about "the computer" is answered from here, and
// nothing anywhere else may pick one on its own. That single rule is the whole
// point: a forged identity is almost never caught on one wrong value, it is
// caught on two values that cannot both be true -- a São Paulo clock beside a
// Frankfurt address, a macOS user agent beside Windows fonts, `screen` the same
// size as the viewport.
//
// This lives in Chromium rather than in the embedder because it is *behaviour*,
// not plumbing. An embedder can only answer the questions CEF thinks to ask it,
// and it answers them one at a time, which is exactly how the values drift
// apart. Here there is one struct, read once, and every consumer derives from
// it.
//
// Not to be confused with the questions that genuinely belong to the host --
// where the card sits on screen, how a dialog should look, where a download
// goes. Those depend on the application and stay at the boundary.
class Identity {
 public:
  // The process-wide identity, resolved on first use.
  static const Identity& Get();

  // IANA zone, e.g. "America/Sao_Paulo". Empty means "use the real one".
  //
  // Applied by seeding ICU, so Intl, Date::getTimezoneOffset() and the printed
  // zone name all come out of the same lookup -- daylight saving included. An
  // override that pins an offset instead is wrong twice a year, and the
  // disagreement between those three readings is trivial for a page to check.
  const std::string& timezone() const { return timezone_; }

  // BCP-47 tag driving navigator.language(s) and Accept-Language. Empty means
  // "use the real one".
  const std::string& locale() const { return locale_; }

  // The brand a page sees in Sec-CH-UA and navigator.userAgentData.
  //
  // A Chromium-branded build omits "Google Chrome" from the list, so the UA
  // string says Chrome while the headers of the very same request say only
  // Chromium. Never empty.
  const std::string& brand() const { return brand_; }

  // Whether any value here was forced rather than observed. Spoofing is
  // coherent only while every surface follows the same source, so code that
  // adds a new surface can assert it consulted this.
  bool is_spoofed() const { return is_spoofed_; }

 private:
  // Constructed once through Get(); NoDestructor needs reach.
  friend class base::NoDestructor<Identity>;

  Identity();

  std::string timezone_;
  std::string locale_;
  std::string brand_;
  bool is_spoofed_ = false;
};

// Applies Identity::timezone() to ICU's default zone. A no-op when the
// identity carries no timezone, so the machine's own is left alone.
//
// Must run after base::i18n::InitializeICU() and before anything reads a
// clock -- in practice, immediately after it in every process.
void ApplyIdentityTimezone();

}  // namespace sofik

#endif  // COMPONENTS_SOFIK_IDENTITY_H_
