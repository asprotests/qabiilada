const express = require("express");
const fs = require("fs");
const readline = require("readline");

const app = express();
const PORT = 3000;
const JSONL_FILE = "./abtirsi_data.jsonl";

app.use(express.static("public")); // Serve frontend

async function readJsonlFile() {
  const people = {};
  const rl = readline.createInterface({
    input: fs.createReadStream(JSONL_FILE),
    crlfDelay: Infinity,
  });

  for await (const line of rl) {
    if (!line.trim()) continue;
    const person = JSON.parse(line);
    people[person.id] = person;
  }

  return people;
}

app.get("/api/tree", async (req, res) => {
  const rootId = parseInt(req.query.id || "0");
  const data = await readJsonlFile();

  function buildTree(id) {
    const node = data[id];
    if (!node) return null;

    let children = [];
    (node.children_groups || []).forEach((group) => {
      (group.children || []).forEach((child) => {
        if (data[child.id]) {
          const childNode = buildTree(child.id);
          if (childNode) children.push(childNode);
        }
      });
    });

    return {
      name: node.name,
      id: node.id,
      children,
    };
  }

  const tree = buildTree(rootId);
  if (!tree) return res.status(404).json({ error: "Not found" });
  res.json(tree);
});

app.listen(PORT, () => {
  console.log(`✅ Tree API live at http://localhost:${PORT}`);
});
