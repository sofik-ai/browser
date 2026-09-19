// Copyright 2026 Sofik. All rights reserved.
//
// The helper executable: every renderer, GPU and utility process is this, and
// all it does is hand itself to the engine.

#include "sofik/engine/sofik_engine.h"

int main(int argc, const char** argv) {
  return sofik_engine_run_child_process(argc, argv);
}
