interface SeoPayload {
  title: string;
  description: string;
  path: string;
}

function upsertMetaByName(name: string, content: string): void {
  let node = document.querySelector<HTMLMetaElement>(`meta[name="${name}"]`);
  if (!node) {
    node = document.createElement("meta");
    node.setAttribute("name", name);
    document.head.appendChild(node);
  }
  node.setAttribute("content", content);
}

function upsertMetaByProperty(property: string, content: string): void {
  let node = document.querySelector<HTMLMetaElement>(`meta[property="${property}"]`);
  if (!node) {
    node = document.createElement("meta");
    node.setAttribute("property", property);
    document.head.appendChild(node);
  }
  node.setAttribute("content", content);
}

export function applySeo(payload: SeoPayload): void {
  const origin = window.location.origin;
  const canonicalUrl = `${origin}${payload.path}`;

  document.title = payload.title;
  upsertMetaByName("description", payload.description);
  upsertMetaByProperty("og:type", "website");
  upsertMetaByProperty("og:title", payload.title);
  upsertMetaByProperty("og:description", payload.description);
  upsertMetaByProperty("og:url", canonicalUrl);
  upsertMetaByProperty("og:site_name", "Asya");
}
