export async function onRequest() {
  return new Response(JSON.stringify({ ok: true, time: Date.now() }), {
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
}
