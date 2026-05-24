export async function onRequest(context) {
  const { request } = context;
  const url = new URL(request.url);
  const target = url.searchParams.get("url");
  if (!target) {
    return new Response("Missing url parameter", { status: 400 });
  }

  const allowedPrefixes = [
    "https://api.bestbuy.com/v1/",
    "https://redsky.target.com/redsky_aggregations/v1/web/",
    "https://api.target.com/fulfillment_aggregator/v1/",
  ];
  const allowed = allowedPrefixes.some((p) => target.startsWith(p));
  if (!allowed) {
    return new Response("URL not allowed", { status: 403 });
  }

  const headers = {};
  for (const [k, v] of request.headers) {
    const lower = k.toLowerCase();
    if (lower.startsWith("cf-") || lower === "host" || lower === "connection") continue;
    headers[k] = v;
  }

  try {
    const resp = await fetch(target, { headers, timeout: 20000 });
    const body = await resp.arrayBuffer();
    const response = new Response(body, {
      status: resp.status,
      statusText: resp.statusText,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Cache-Control": "public, max-age=60",
      },
    });
    for (const [k, v] of resp.headers) {
      const lower = k.toLowerCase();
      if (lower === "access-control-allow-origin" || lower === "content-encoding" || lower === "transfer-encoding") continue;
      response.headers.set(k, v);
    }
    return response;
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 502,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });
  }
}
