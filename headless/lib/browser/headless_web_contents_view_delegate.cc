// Copyright 2026 Sofik. All rights reserved.

#include "headless/lib/browser/headless_web_contents_view_delegate.h"

#include "content/public/browser/context_menu_params.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/web_contents.h"
#include "headless/lib/browser/headless_web_contents_impl.h"
#include "headless/public/headless_embedder_delegate.h"

namespace headless {

HeadlessWebContentsViewDelegate::HeadlessWebContentsViewDelegate(
    content::WebContents* web_contents)
    : web_contents_(web_contents) {}

HeadlessWebContentsViewDelegate::~HeadlessWebContentsViewDelegate() = default;

void HeadlessWebContentsViewDelegate::ShowContextMenu(
    content::RenderFrameHost& render_frame_host,
    const content::ContextMenuParams& params) {
  // Looked up now, not at construction: the view delegate is made while the
  // web contents is, before headless knows it.
  HeadlessWebContentsImpl* contents =
      HeadlessWebContentsImpl::From(web_contents_);
  if (contents && contents->embedder_delegate()) {
    contents->embedder_delegate()->OnContextMenu(render_frame_host, params);
  }
}

}  // namespace headless
