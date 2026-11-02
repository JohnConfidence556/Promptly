import JSZip from "jszip";

export async function downloadZip(
  title: string,
  version: number,
  files: Record<string, string>,
): Promise<void> {
  const slug =
    title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || "app";

  const zip = new JSZip();
  const folder = zip.folder(slug) ?? zip;
  for (const [name, content] of Object.entries(files)) {
    folder.file(name, content);
  }

  const blob = await zip.generateAsync({ type: "blob" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = `${slug}-v${version}.zip`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}