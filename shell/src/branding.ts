// Tenant branding comes from Agent Authority (GET /api/authority/branding, proxied by the
// control plane as /branding). One place to brand both products. The shell sets no brand
// overrides of its own on <agent-authority>, so the two always match. Meaning colours
// (verdict, status, node kind) are locked on Agent Authority's side and never come from here.

export interface Branding {
  productName: string;
  logoUrl?: string;
  monogram?: string;
  faviconUrl?: string;
  css?: string; // brand tokens only, applied under :root
}

export const DEFAULT_BRANDING: Branding = { productName: "App Builder" };

export async function loadBranding(fetchImpl: typeof fetch = fetch): Promise<Branding> {
  try {
    const res = await fetchImpl("/api/branding");
    if (!res.ok) return DEFAULT_BRANDING;
    const body = await res.json();
    if (body?.source === "defaults" || typeof body?.productName !== "string") return DEFAULT_BRANDING;
    return body as Branding;
  } catch {
    // Branding is cosmetic: never block the app on it.
    return DEFAULT_BRANDING;
  }
}

export function applyBranding(b: Branding, doc: Document = document): void {
  doc.title = b.productName;
  if (b.faviconUrl) doc.getElementById("favicon")?.setAttribute("href", b.faviconUrl);
  if (b.css) {
    const style = doc.getElementById("tenant-branding") ?? doc.head.appendChild(doc.createElement("style"));
    style.id = "tenant-branding";
    style.textContent = b.css;
  }
}
