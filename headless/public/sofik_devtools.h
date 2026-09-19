// Copyright 2026 Sofik. All rights reserved.

#ifndef HEADLESS_PUBLIC_SOFIK_DEVTOOLS_H_
#define HEADLESS_PUBLIC_SOFIK_DEVTOOLS_H_

namespace headless {

// Sofik: where an embedded browser finds the DevTools front end.
//
// The front end is already inside the browser's resources. Chrome serves it
// on devtools://, through WebUI, which is //chrome; content_shell and
// headless serve it over HTTP on the remote debugging port, and a port on
// localhost is a thing any page can probe for. This scheme serves the same
// bundled files to a page of the embedder's own and listens nowhere.
inline constexpr char kSofikDevToolsScheme[] = "sofik-devtools";
inline constexpr char kSofikDevToolsHost[] = "devtools";
// kSofikDevToolsFrontendURL + "?..." is the page to load.
inline constexpr char kSofikDevToolsFrontendURL[] =
    "sofik-devtools://devtools/bundled/devtools_app.html";

}  // namespace headless

#endif  // HEADLESS_PUBLIC_SOFIK_DEVTOOLS_H_
