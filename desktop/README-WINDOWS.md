# Fireflies Clone — Desktop packaging\n\nThe Electron main process launches the bundled backend executable automatically and serves the static Next.js export through an internal loopback HTTP server. This avoids `file://` asset/path problems in packaged Next.js exports.\n\nThe backend database lives under Electron `app.getPath('userData')`, so installed/portable runs do not write to the application bundle.\n

## Meeting AI
AskFred and meeting analysis use the configured OpenAI API key for full LLM responses. Add or replace the key from Profile → Settings → Meeting AI. Without a key, chat uses grounded retrieval only and never invokes a small generative chat model. The default model is `gpt-5.6-luna`.
