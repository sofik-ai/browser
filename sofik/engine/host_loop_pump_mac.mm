// Copyright 2026 Sofik. All rights reserved.

#include <CoreFoundation/CoreFoundation.h>
#include <pthread.h>

#include <limits>
#include <memory>
#include <utility>

#include "base/apple/scoped_cftyperef.h"
#include "base/apple/scoped_nsautorelease_pool.h"
#include "base/message_loop/message_pump.h"
#include "base/message_loop/message_pump_apple.h"
#include "base/run_loop.h"
#include "base/time/time.h"
#include "sofik/engine/engine.h"

namespace sofik {
namespace {

// A UI message pump for a thread whose loop belongs to somebody else.
//
// Chromium's own pumps are handed their delegate inside Run(), and Run() is
// the one call an embedded engine never makes: the loop on the main thread is
// AppKit's, under Flutter. So this pump does no looping of its own. When the
// engine has work it signals a source on the main CFRunLoop, the host's loop
// wakes, and the source runs the engine's tasks until it is idle and returns.
//
// CEF reaches the same place by asking the embedder to poll
// (OnScheduleMessagePumpWork / CefDoMessageLoopWork). Signalling the run loop
// directly leaves nothing for the host to get wrong.
class HostLoopMessagePump : public base::MessagePump {
 public:
  HostLoopMessagePump() {
    CFRunLoopSourceContext source_context = {};
    source_context.info = this;
    source_context.perform = &HostLoopMessagePump::OnWork;
    work_source_.reset(CFRunLoopSourceCreate(kCFAllocatorDefault,
                                             /*order=*/1, &source_context));
    CFRunLoopAddSource(CFRunLoopGetMain(), work_source_.get(),
                       kCFRunLoopCommonModes);

    CFRunLoopTimerContext timer_context = {};
    timer_context.info = this;
    delayed_timer_.reset(CFRunLoopTimerCreate(
        kCFAllocatorDefault, /*fireDate=*/kNever,
        /*interval=*/kNever, /*flags=*/0, /*order=*/0,
        &HostLoopMessagePump::OnTimer, &timer_context));
    CFRunLoopAddTimer(CFRunLoopGetMain(), delayed_timer_.get(),
                      kCFRunLoopCommonModes);
  }

  HostLoopMessagePump(const HostLoopMessagePump&) = delete;
  HostLoopMessagePump& operator=(const HostLoopMessagePump&) = delete;

  ~HostLoopMessagePump() override {
    CFRunLoopRemoveTimer(CFRunLoopGetMain(), delayed_timer_.get(),
                         kCFRunLoopCommonModes);
    CFRunLoopRemoveSource(CFRunLoopGetMain(), work_source_.get(),
                          kCFRunLoopCommonModes);
  }

  // base::MessagePump:
  void Run(Delegate* delegate) override {
    // Entered through RunLoop::RunUntilIdle() from Drain(), never to block.
    bool was_running = std::exchange(running_, true);
    const base::TimeTicks deadline = base::TimeTicks::Now() + kTimeSlice;
    quit_ = false;
    while (!quit_) {
      base::apple::ScopedNSAutoreleasePool pool;
      Delegate::NextWorkInfo next = delegate->DoWork();
      if (next.is_immediate()) {
        // Give the host's own events a turn rather than starve its UI, and
        // come straight back.
        if (base::TimeTicks::Now() >= deadline) {
          ScheduleWork();
          break;
        }
        continue;
      }
      delegate->DoIdleWork();
      if (!next.delayed_run_time.is_max()) {
        ScheduleDelayedWork(next);
      }
      break;
    }
    running_ = was_running;
  }

  void Quit() override { quit_ = true; }

  void ScheduleWork() override {
    CFRunLoopSourceSignal(work_source_.get());
    CFRunLoopWakeUp(CFRunLoopGetMain());
  }

  void ScheduleDelayedWork(const Delegate::NextWorkInfo& next) override {
    base::TimeDelta delay = next.remaining_delay();
    CFRunLoopTimerSetNextFireDate(
        delayed_timer_.get(),
        CFAbsoluteTimeGetCurrent() + delay.InSecondsF());
  }

 private:
  static constexpr base::TimeDelta kTimeSlice = base::Milliseconds(8);
  // A timer that is armed only by ScheduleDelayedWork().
  static constexpr CFTimeInterval kNever =
      std::numeric_limits<CFTimeInterval>::max();

  static void OnWork(void* info) {
    static_cast<HostLoopMessagePump*>(info)->Drain();
  }
  static void OnTimer(CFRunLoopTimerRef, void* info) {
    static_cast<HostLoopMessagePump*>(info)->Drain();
  }

  void Drain() {
    if (running_) {
      // A nested host loop (a menu, a modal sheet) re-entered us.
      return;
    }
    base::RunLoop(base::RunLoop::Type::kNestableTasksAllowed).RunUntilIdle();
  }

  base::apple::ScopedCFTypeRef<CFRunLoopSourceRef> work_source_;
  base::apple::ScopedCFTypeRef<CFRunLoopTimerRef> delayed_timer_;
  bool running_ = false;
  bool quit_ = false;
};

std::unique_ptr<base::MessagePump> CreateHostLoopMessagePump() {
  // The factory is asked for every UI-type pump in the process, not only the
  // browser's: on macOS the thread that watches the network configuration
  // wants one too, because it needs a CFRunLoop. Only the main thread's loop
  // belongs to the host. Handing this pump to another thread makes that
  // thread's Run() return at once, and it dies on the spot.
  if (!pthread_main_np()) {
    return base::message_pump_apple::Create();
  }
  return std::make_unique<HostLoopMessagePump>();
}

}  // namespace

void InstallHostLoopMessagePump() {
  base::MessagePump::OverrideMessagePumpForUIFactory(
      &CreateHostLoopMessagePump);
}

}  // namespace sofik
