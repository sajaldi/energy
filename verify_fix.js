
const msg = $node["Variables"].json.mensaje_original || "";

function extract(regex, defaultVal = "") {
  const match = msg.match(regex);
  return (match && match[1]) ? match[1].trim() : defaultVal;
}

// Regex more robust as suggested by user
const diagnostico = extract(/Diagn[oó]stico:[ ]*([^\n\r-]+)/i, msg);
const actividades = extract(/Acci[oó]n realizada:[ ]*([^\n\r-]+)/i, "Ver diagnóstico");
const hi_str = extract(/HI:[ ]*([^\n\r-]+)/i, "");
const hf_str = extract(/HF:[ ]*([^\n\r-]+)/i, "");
const observaciones = extract(/Observa[cv]iones:[ ]*([^\n\r-]+)/i, "Ninguna");
const uf = extract(/UF:[ ]*([^\n\r-]+)/i, "N/A");

return {
  diagnostico,
  actividades,
  hi_str,
  hf_str,
  observaciones,
  uf
};
