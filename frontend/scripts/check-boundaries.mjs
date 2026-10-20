import { readdir, readFile } from "node:fs/promises";
import { dirname, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = fileURLToPath(new URL("../src/", import.meta.url));

async function sourceFiles(folder) {
  const entries = await readdir(folder, { withFileTypes: true });
  const nested = await Promise.all(
    entries.map((entry) => {
      const path = resolve(folder, entry.name);
      return entry.isDirectory()
        ? sourceFiles(path)
        : /\.[cm]?[jt]sx?$/.test(entry.name)
          ? [path]
          : [];
    }),
  );
  return nested.flat();
}

function parts(file) {
  return relative(root, file).split(sep);
}

function allowed(origin, target) {
  const [layer, feature] = parts(origin);
  const [dependency, dependencyFeature] = parts(target);
  if (dependency === "..") return false;
  if (layer === "shared")
    return dependency === "shared" || dependency === "styles";
  if (layer === "layouts")
    return ["layouts", "shared", "styles"].includes(dependency);
  if (layer === "features")
    return (
      ["shared", "styles"].includes(dependency) ||
      (dependency === "features" && feature === dependencyFeature)
    );
  return true;
}

const failures = [];
const files = await sourceFiles(root);
for (const file of files) {
  const imports = ts.preProcessFile(
    await readFile(file, "utf8"),
    true,
    true,
  ).importedFiles;
  for (const { fileName } of imports) {
    const target = fileName.startsWith("@/")
      ? resolve(root, fileName.slice(2))
      : fileName.startsWith(".")
        ? resolve(dirname(file), fileName)
        : null;
    if (target && !allowed(file, target))
      failures.push(`${relative(root, file)} → ${fileName}`);
  }
}
if (failures.length) {
  console.error(
    `Dependências entre camadas inválidas:\n${failures.join("\n")}`,
  );
  process.exitCode = 1;
} else
  console.log(`Fronteiras verificadas em ${files.length} arquivos de código.`);
