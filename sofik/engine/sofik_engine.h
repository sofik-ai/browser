/* Copyright 2026 Sofik. All rights reserved.
 *
 * The Sofik engine: a browser for agents, as a C API.
 *
 * This is the whole surface the Browser Card needs from a browser. It was
 * sized from what the webview_cef plugin actually uses of CEF -- 15 handler
 * interfaces, about 50 callbacks -- not from what CEF offers, which is a few
 * thousand entry points over Chrome's entire product layer. Underneath is
 * Chromium's content layer and nothing above it: no //chrome, no CEF.
 *
 * Plain C, no C++ types across the boundary. The engine is built with
 * Chromium's own libc++ under a private ABI namespace, and the plugin with the
 * platform toolchain, so C is the only ABI the two can share. (CEF has the
 * same constraint and answers it with a C API plus a C++ wrapper every
 * embedder must compile for itself; here the C API is the API.)
 *
 * Threading follows what the plugin already does with CEF. On macOS the engine
 * lives on the application's main thread and attaches to its run loop: call
 * everything from the main thread, callbacks arrive on it. On Windows and
 * Linux the engine runs a UI thread of its own: calls may come from any
 * thread and are posted to it, callbacks arrive on the engine's thread.
 *
 * Status. macOS only so far. Wired: process and lifecycle, views with a size
 * and a scale of their own, GPU and software frames (a <select> drop-down is
 * already composited into them), navigation, mouse, wheel, keyboard and IME,
 * the address, title, favicon, loading, load-error, console, cursor, tooltip,
 * focused-node, IME-bounds and closed events, new-window requests, JavaScript
 * dialogs (alert, confirm, prompt, beforeunload), downloads, permission
 * prompts, file choosers, navigation vetoes, and the DevTools session.
 * Everything declared here is delivered.
 */

#ifndef SOFIK_ENGINE_SOFIK_ENGINE_H_
#define SOFIK_ENGINE_SOFIK_ENGINE_H_

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#if defined(SOFIK_ENGINE_IMPLEMENTATION)
#define SOFIK_EXPORT __declspec(dllexport)
#else
#define SOFIK_EXPORT __declspec(dllimport)
#endif
#else
#define SOFIK_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Bumped on any incompatible change. sofik_engine_initialize refuses a
 * settings struct built against a different one. */
#define SOFIK_ENGINE_ABI 2

typedef uint32_t sofik_view_id; /* 0 is never a valid view. */

/* ---- process ------------------------------------------------------------ */

/* Entry point of the helper executable: renderer, GPU and utility processes
 * are this same engine, started with --type=. Returns the exit code. In the
 * browser process it returns -1 at once and the host carries on. */
SOFIK_EXPORT int sofik_engine_run_child_process(int argc, const char** argv);

typedef struct sofik_settings {
  uint32_t abi;                 /* SOFIK_ENGINE_ABI */
  const char* helper_path;      /* executable that calls run_child_process */
  /* icudtl.dat, the .pak files and the V8 snapshots. NULL: the directory of
   * the engine's library, which is where a distribution puts them. */
  const char* resources_dir;
  const char* cache_root;       /* profiles live under it */
  const char* locale;           /* UI locale, e.g. "pt-BR" */
  const char* accept_languages; /* "pt-BR,pt,en-US,en" */
  /* The identity a page sees. NULL leaves the engine's own defaults, which
   * are those of the Chrome release this engine descends from. */
  const char* user_agent;
  const char* extra_switches;   /* space separated, for diagnostics */
  int remote_debugging_port;    /* 0 = off */
  /* The scale of a view that does not name one. 0 means 1.0. */
  float device_scale_factor;
} sofik_settings;

/* Non-blocking: returns once the engine is up. 0 on success. */
SOFIK_EXPORT int sofik_engine_initialize(const sofik_settings* settings);
SOFIK_EXPORT void sofik_engine_shutdown(void);

/* ---- frames -------------------------------------------------------------- */

typedef enum sofik_pixel_format {
  SOFIK_PIXEL_BGRA = 0,
  SOFIK_PIXEL_RGBA = 1,
} sofik_pixel_format;

typedef struct sofik_rect {
  int x, y, width, height;
} sofik_rect;

typedef struct sofik_frame {
  int width, height;          /* of the texture or buffer, in pixels */
  sofik_rect content;         /* where the page is inside it */
  sofik_rect damage;          /* what changed since the previous frame */
  sofik_pixel_format format;
  /* Exactly one of the following is set.
   *
   * A GPU frame stays valid until the *next* frame for the same view is
   * delivered, not merely for the duration of the callback. That is how a
   * presented texture is consumed -- show the latest, swap when a newer one
   * lands -- and it spares the host a blocking full-frame copy. */
  void* io_surface;           /* macOS: IOSurfaceRef */
  void* dxgi_shared_handle;   /* Windows: HANDLE */
  int dmabuf_fd;              /* Linux: -1 when unused */
  int dmabuf_stride, dmabuf_offset;
  uint64_t dmabuf_modifier;
  const uint8_t* pixels;      /* software fallback, valid during the call */
  int stride;
} sofik_frame;

/* ---- events -------------------------------------------------------------- */

typedef enum sofik_cursor {
  SOFIK_CURSOR_POINTER = 0, SOFIK_CURSOR_HAND, SOFIK_CURSOR_IBEAM,
  SOFIK_CURSOR_CROSS, SOFIK_CURSOR_WAIT, SOFIK_CURSOR_NOT_ALLOWED,
  SOFIK_CURSOR_GRAB, SOFIK_CURSOR_GRABBING, SOFIK_CURSOR_RESIZE_EW,
  SOFIK_CURSOR_RESIZE_NS, SOFIK_CURSOR_RESIZE_NESW, SOFIK_CURSOR_RESIZE_NWSE,
  SOFIK_CURSOR_NONE, SOFIK_CURSOR_MOVE, SOFIK_CURSOR_HELP,
  SOFIK_CURSOR_PROGRESS, SOFIK_CURSOR_COPY, SOFIK_CURSOR_ALIAS,
  SOFIK_CURSOR_CONTEXT_MENU, SOFIK_CURSOR_CELL, SOFIK_CURSOR_VERTICAL_TEXT,
  SOFIK_CURSOR_ZOOM_IN, SOFIK_CURSOR_ZOOM_OUT, SOFIK_CURSOR_RESIZE_COLUMN,
  SOFIK_CURSOR_RESIZE_ROW,
  /* An image of the page's own (cursor: url(...)). Shown as a pointer until
   * the API carries the bitmap. */
  SOFIK_CURSOR_CUSTOM,
} sofik_cursor;

typedef enum sofik_dialog_kind {
  SOFIK_DIALOG_ALERT = 0, SOFIK_DIALOG_CONFIRM, SOFIK_DIALOG_PROMPT,
  SOFIK_DIALOG_BEFORE_UNLOAD,
} sofik_dialog_kind;

typedef enum sofik_permission {
  SOFIK_PERMISSION_CAMERA = 1 << 0,
  SOFIK_PERMISSION_MICROPHONE = 1 << 1,
  SOFIK_PERMISSION_GEOLOCATION = 1 << 2,
  SOFIK_PERMISSION_NOTIFICATIONS = 1 << 3,
  SOFIK_PERMISSION_CLIPBOARD = 1 << 4,
  SOFIK_PERMISSION_SCREEN_CAPTURE = 1 << 5,
} sofik_permission;

typedef struct sofik_download {
  uint32_t id;
  const char* url;
  const char* suggested_name; /* chosen by the page: treat as hostile */
  const char* mime_type;
  const char* path;           /* where it is being written, once known */
  int64_t received_bytes, total_bytes; /* total is -1 when unknown */
  int is_complete, is_canceled, is_interrupted;
} sofik_download;

/* Every callback may be NULL. `user` is the pointer given at creation.
 * Strings are UTF-8 and owned by the engine: copy what must outlive the call.
 * A request the host does not answer stays pending, and a pending one blocks
 * the page -- answer every request, even if only to decline. */
typedef struct sofik_view_callbacks {
  void (*on_frame)(void* user, sofik_view_id, const sofik_frame*);
  void (*on_cursor)(void* user, sofik_view_id, sofik_cursor);

  void (*on_address_changed)(void* user, sofik_view_id, const char* url);
  void (*on_title_changed)(void* user, sofik_view_id, const char* title);
  void (*on_favicon_changed)(void* user, sofik_view_id, const char* url);
  void (*on_loading_state)(void* user, sofik_view_id, int is_loading,
                           int can_go_back, int can_go_forward);
  void (*on_load_error)(void* user, sofik_view_id, int error_code,
                        const char* error_text, const char* url);
  void (*on_console_message)(void* user, sofik_view_id, int level,
                             const char* message, const char* source, int line);
  /* "" when there is no tooltip any more. */
  void (*on_tooltip)(void* user, sofik_view_id, const char* text);
  /* Focus entered or left a text field, or the caret moved inside one.
   * `caret` is in DIPs relative to the view: where an input method's
   * candidate window belongs before there is a composition. */
  void (*on_focused_node_changed)(void* user, sofik_view_id, int is_editable,
                                  sofik_rect caret);
  /* The text being composed, in DIPs relative to the view. */
  void (*on_ime_composition_bounds)(void* user, sofik_view_id, sofik_rect bounds);

  /* Return non-zero to cancel. Asked for every request of the main frame and
   * every redirect of it, except the URL the view was created with. A popup
   * is never opened by the engine itself:
   * the host decides, usually by loading `url` in a view of its own. */
  int (*on_before_navigation)(void* user, sofik_view_id, const char* url,
                              int is_user_gesture, int is_redirect);
  void (*on_popup_requested)(void* user, sofik_view_id, const char* url,
                             int is_user_gesture);

  /* Answer with sofik_view_answer_*. */
  void (*on_dialog)(void* user, sofik_view_id, uint32_t request,
                    sofik_dialog_kind, const char* message,
                    const char* default_prompt);
  void (*on_file_dialog)(void* user, sofik_view_id, uint32_t request,
                         int allow_multiple, int is_folder,
                         const char* accept_types);
  void (*on_permission_request)(void* user, sofik_view_id, uint32_t request,
                                const char* origin, uint32_t permissions);
  void (*on_download_requested)(void* user, sofik_view_id, uint32_t request,
                                const sofik_download*);
  void (*on_download_updated)(void* user, sofik_view_id, const sofik_download*);

  void (*on_closed)(void* user, sofik_view_id);
} sofik_view_callbacks;

/* ---- views --------------------------------------------------------------- */

typedef struct sofik_view_config {
  const char* url;
  int width, height;          /* in DIPs */
  int frame_rate;             /* frames per second, 60 if 0 */
  /* Storage partition: cookies, cache, local storage. One directory per
   * profile under cache_root; NULL is an off-the-record profile. */
  const char* profile;
  int prefer_gpu_frames;      /* shared texture instead of pixels */
  /* Pixels per DIP of this view: the density of whatever the host composites
   * the texture onto. 0 takes sofik_settings.device_scale_factor. */
  float device_scale_factor;
  /* Non-zero: a native view instead of frames (macOS only so far). The page
   * is drawn by the window server inside a view the host places in its own
   * window -- see sofik_view_native_handle. Sharp at any zoom of whatever is
   * around it, which a resampled texture never is, at the price of being a
   * rectangle on top of the host's content rather than part of it. The
   * platform then delivers the person's mouse, keyboard, input method, cursor,
   * tooltips and <select> menus by itself: on_frame, on_cursor, on_tooltip and
   * the IME callbacks stay silent, and the sofik_view_mouse_*, _key, _ime_*,
   * _resize and _set_scale functions do nothing. An agent drives the page
   * through DevTools in both modes. */
  int native_view;
} sofik_view_config;

SOFIK_EXPORT sofik_view_id sofik_view_create(const sofik_view_config*,
                                             const sofik_view_callbacks*,
                                             void* user);
SOFIK_EXPORT void sofik_view_close(sofik_view_id);

/* For a view created with native_view: the NSView* (macOS) to add to the
 * host's window and to size like any other. The engine owns it; it is gone
 * after sofik_view_close or on_closed, and so has to be removed from its
 * superview before either. NULL for a view that delivers frames. */
SOFIK_EXPORT void* sofik_view_native_handle(sofik_view_id);

SOFIK_EXPORT void sofik_view_resize(sofik_view_id, int width, int height);
/* The window moved to a monitor of another density. */
SOFIK_EXPORT void sofik_view_set_scale(sofik_view_id, float device_scale_factor);
SOFIK_EXPORT void sofik_view_set_visible(sofik_view_id, int visible);
SOFIK_EXPORT void sofik_view_set_focus(sofik_view_id, int focused);
SOFIK_EXPORT void sofik_view_invalidate(sofik_view_id);

SOFIK_EXPORT void sofik_view_load_url(sofik_view_id, const char* url);
SOFIK_EXPORT void sofik_view_go_back(sofik_view_id);
SOFIK_EXPORT void sofik_view_go_forward(sofik_view_id);
SOFIK_EXPORT void sofik_view_reload(sofik_view_id, int ignore_cache);
SOFIK_EXPORT void sofik_view_stop(sofik_view_id);
SOFIK_EXPORT void sofik_view_set_zoom(sofik_view_id, double level);

/* ---- input --------------------------------------------------------------- */

enum {
  SOFIK_MOD_SHIFT = 1 << 0, SOFIK_MOD_CONTROL = 1 << 1, SOFIK_MOD_ALT = 1 << 2,
  SOFIK_MOD_META = 1 << 3, SOFIK_MOD_LEFT_BUTTON = 1 << 4,
  SOFIK_MOD_MIDDLE_BUTTON = 1 << 5, SOFIK_MOD_RIGHT_BUTTON = 1 << 6,
  SOFIK_MOD_IS_REPEAT = 1 << 7,
};

typedef enum sofik_mouse_button {
  SOFIK_BUTTON_LEFT = 0, SOFIK_BUTTON_MIDDLE, SOFIK_BUTTON_RIGHT,
} sofik_mouse_button;

typedef enum sofik_key_type {
  SOFIK_KEY_RAW_DOWN = 0, SOFIK_KEY_UP, SOFIK_KEY_CHAR,
} sofik_key_type;

/* Coordinates are in DIPs, relative to the view. */
SOFIK_EXPORT void sofik_view_mouse_move(sofik_view_id, int x, int y,
                                        uint32_t modifiers, int left_the_view);
SOFIK_EXPORT void sofik_view_mouse_button(sofik_view_id, int x, int y,
                                          sofik_mouse_button, int is_up,
                                          int click_count, uint32_t modifiers);
SOFIK_EXPORT void sofik_view_mouse_wheel(sofik_view_id, int x, int y,
                                         float delta_x, float delta_y,
                                         uint32_t modifiers);
SOFIK_EXPORT void sofik_view_key(sofik_view_id, sofik_key_type,
                                 int windows_key_code, int native_key_code,
                                 uint32_t character, uint32_t modifiers);

/* Text input through an input method. The selection is in UTF-16 code units
 * inside `text`, as the platform's input APIs report it. */
SOFIK_EXPORT void sofik_view_ime_set_composition(sofik_view_id,
                                                 const char* text,
                                                 int selection_start,
                                                 int selection_end);
SOFIK_EXPORT void sofik_view_ime_commit(sofik_view_id, const char* text);
SOFIK_EXPORT void sofik_view_ime_cancel(sofik_view_id);

/* ---- answers ------------------------------------------------------------- */

SOFIK_EXPORT void sofik_view_answer_dialog(sofik_view_id, uint32_t request,
                                           int accepted, const char* prompt);
/* `paths` is `count` UTF-8 strings; count 0 cancels. For a folder request it
 * is the one folder, and the engine lists the files under it. */
SOFIK_EXPORT void sofik_view_answer_file_dialog(sofik_view_id, uint32_t request,
                                                const char* const* paths,
                                                size_t count);
/* `granted` is the subset of the requested sofik_permission bits. */
SOFIK_EXPORT void sofik_view_answer_permission(sofik_view_id, uint32_t request,
                                               uint32_t granted);
/* NULL path declines the download. */
SOFIK_EXPORT void sofik_view_answer_download(sofik_view_id, uint32_t request,
                                             const char* path);
SOFIK_EXPORT void sofik_view_cancel_download(sofik_view_id, uint32_t download);

/* ---- scripting ----------------------------------------------------------- */

/* DevTools protocol, the way an agent drives the page -- including running
 * script, which is Runtime.evaluate: the content layer only lets an embedder
 * inject script directly into its own internal pages. One session per view;
 * messages and events are JSON, exactly as on the wire. */
typedef void (*sofik_cdp_callback)(void* user, sofik_view_id,
                                   const char* message_json);
SOFIK_EXPORT void sofik_view_cdp_attach(sofik_view_id, sofik_cdp_callback,
                                        void* user);
SOFIK_EXPORT void sofik_view_cdp_send(sofik_view_id, const char* message_json);
SOFIK_EXPORT void sofik_view_cdp_detach(sofik_view_id);

#ifdef __cplusplus
}
#endif

#endif /* SOFIK_ENGINE_SOFIK_ENGINE_H_ */
