export function getGenerationStatusClass(status) {
  if (status === "completed") return "ready";
  if (status === "failed") return "failed";
  return "";
}
