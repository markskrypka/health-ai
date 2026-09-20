import { readFile, writeFile, readdir } from "node:fs/promises";
import { join, resolve } from "node:path";

const projectDir = resolve(import.meta.dirname, "..");
const framesDir = join(projectDir, "compositions", "frames");

const fontFaceDecl = `
      @font-face {
        font-family: 'Geist';
        src: local('Geist'), local('Inter'), local('system-ui');
      }
`;

const files = await readdir(framesDir);
for (const f of files) {
  if (!f.endsWith(".html")) continue;
  const p = join(framesDir, f);
  let content = await readFile(p, "utf8");

  if (!content.includes("@font-face")) {
    content = content.replace("<style>", `<style>${fontFaceDecl}`);
  }

  if (f === "01-hook.html") {
    // Fix Math.random and repeat: -1
    content = content.replace(
      /height: \(\) => 15 \+ Math\.random\(\) \* 65,[\s\S]*?repeat: -1,/,
      `height: (i) => 15 + ((Math.sin(i * 12.3) * 0.5 + 0.5) * 65),
        backgroundColor: (i) => ((i % 3 === 0) ? "#0f6b5c" : "#34d399"),
        repeat: 60,`
    );
  }

  await writeFile(p, content);
  console.log(`Updated ${f}`);
}
