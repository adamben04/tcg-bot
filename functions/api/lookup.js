export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const zip = url.searchParams.get("zip") || "none";

  const result = {
    ok: true,
    zip,
    targetCount: 14,
    bestbuyCount: 2,
    targetKey: (env.TARGET_API_KEY || "").slice(0, 8) + "...",
    bestbuyKey: (env.BESTBUY_API_KEY || "").slice(0, 8) + "...",
  };

  return new Response(JSON.stringify(result), {
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
}
