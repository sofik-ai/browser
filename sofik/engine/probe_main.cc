// Copyright 2026 Sofik. All rights reserved.

#include "build/build_config.h"
#include "content/public/app/content_main.h"
#include "sofik/engine/probe.h"

#if BUILDFLAG(IS_WIN)
#include "content/public/app/sandbox_helper_win.h"
#include "sandbox/win/src/sandbox_types.h"  // nogncheck
#elif BUILDFLAG(IS_MAC)
#include "base/check.h"
#include "sandbox/mac/seatbelt_exec.h"
#endif

int main(int argc, const char** argv) {
  content::ContentMainParams params(nullptr);
#if BUILDFLAG(IS_WIN)
  sandbox::SandboxInterfaceInfo sandbox_info = {nullptr};
  content::InitializeSandboxInfo(&sandbox_info);
  params.sandbox_info = &sandbox_info;
#else
  params.argc = argc;
  params.argv = argv;
#if BUILDFLAG(IS_MAC)
  // Child processes re-exec this binary; the sandbox has to be entered before
  // anything else runs in them.
  sandbox::SeatbeltExecServer::CreateFromArgumentsResult seatbelt =
      sandbox::SeatbeltExecServer::CreateFromArguments(
          argv[0], argc, const_cast<char**>(argv));
  if (seatbelt.sandbox_required) {
    CHECK(seatbelt.server->InitializeSandbox());
  }
#endif
#endif
  return sofik::ProbeMain(std::move(params));
}
