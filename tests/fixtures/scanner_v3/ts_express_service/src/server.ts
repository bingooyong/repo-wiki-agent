import express from "express";

const app = express();

app.get("/api/hello", (_req, res) => {
  res.json({ ok: true });
});

app.listen(3000);
