// Run pandoc.wasm (a WASI command module) with Node's WASI implementation:
//
//   node run-wasm.mjs pandoc.wasm [pandoc args...]
//
// stdin/stdout/stderr are shared with this process and the current directory
// is preopened as ".". Node (V8) runs both the legacy and the current
// exception-handling encodings that different GHC wasm toolchains emit;
// wasmtime only runs the current one.
import { readFile } from "node:fs/promises";
import { WASI } from "node:wasi";

const [path, ...args] = process.argv.slice(2);
const wasi = new WASI({
  version: "preview1",
  args: ["pandoc", ...args],
  // No PWD: GHC's RTS chdirs to it, and host paths are not visible in WASI.
  env: {},
  preopens: { ".": "." },
  returnOnExit: true,
});
const module = await WebAssembly.compile(await readFile(path));
const instance = await WebAssembly.instantiate(module, wasi.getImportObject());
process.exitCode = wasi.start(instance);
