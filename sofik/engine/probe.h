// Copyright 2026 Sofik. All rights reserved.

#ifndef SOFIK_ENGINE_PROBE_H_
#define SOFIK_ENGINE_PROBE_H_

#include "content/public/app/content_main.h"

namespace sofik {

// sofik_engine_probe --frame-out=/path/frame.png [--settle-ms=1500] <url>
int ProbeMain(content::ContentMainParams params);

}  // namespace sofik

#endif  // SOFIK_ENGINE_PROBE_H_
