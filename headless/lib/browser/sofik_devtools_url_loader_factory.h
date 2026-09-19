// Copyright 2026 Sofik. All rights reserved.

#ifndef HEADLESS_LIB_BROWSER_SOFIK_DEVTOOLS_URL_LOADER_FACTORY_H_
#define HEADLESS_LIB_BROWSER_SOFIK_DEVTOOLS_URL_LOADER_FACTORY_H_

#include "mojo/public/cpp/bindings/pending_receiver.h"
#include "mojo/public/cpp/bindings/pending_remote.h"
#include "services/network/public/cpp/self_deleting_url_loader_factory.h"
#include "services/network/public/mojom/url_loader_factory.mojom.h"

namespace headless {

// Answers sofik-devtools://devtools/bundled/<path> with the DevTools front-end
// file of that path, out of the browser's own resources. See
// headless/public/sofik_devtools.h.
class SofikDevToolsURLLoaderFactory
    : public network::SelfDeletingURLLoaderFactory {
 public:
  static mojo::PendingRemote<network::mojom::URLLoaderFactory> Create();

  SofikDevToolsURLLoaderFactory(const SofikDevToolsURLLoaderFactory&) = delete;
  SofikDevToolsURLLoaderFactory& operator=(
      const SofikDevToolsURLLoaderFactory&) = delete;

 private:
  explicit SofikDevToolsURLLoaderFactory(
      mojo::PendingReceiver<network::mojom::URLLoaderFactory> receiver);
  ~SofikDevToolsURLLoaderFactory() override;

  // network::mojom::URLLoaderFactory:
  void CreateLoaderAndStart(
      mojo::PendingReceiver<network::mojom::URLLoader> loader,
      int32_t request_id,
      uint32_t options,
      const network::ResourceRequest& request,
      mojo::PendingRemote<network::mojom::URLLoaderClient> client,
      const net::MutableNetworkTrafficAnnotationTag& traffic_annotation)
      override;
};

}  // namespace headless

#endif  // HEADLESS_LIB_BROWSER_SOFIK_DEVTOOLS_URL_LOADER_FACTORY_H_
