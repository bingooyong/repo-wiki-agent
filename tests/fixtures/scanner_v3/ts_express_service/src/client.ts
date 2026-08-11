import axios from "axios";

export async function load() {
  const r = await axios.get("/api/hello");
  return r.data;
}
