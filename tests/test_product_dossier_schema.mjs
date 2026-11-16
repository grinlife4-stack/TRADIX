import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const schema = JSON.parse(readFileSync(new URL("../../schemas/product-dossier-v1.schema.json", import.meta.url), "utf8"));
const ajv = new Ajv2020({ allErrors: true, strict: true });
addFormats(ajv);
const validate = ajv.compile(schema);

const common = {
  schema_version: 1,
  mission: "A product-specific mission",
  requirements: [{ id: "REQ-1", statement: "A traceable requirement" }],
  acceptance_criteria: [{ id: "AC-1", test: "A verifiable acceptance condition" }],
  lifecycle: { state: "discovery", created_at: "2026-11-16T12:00:00Z", target_date: "2027-01-31" }
};

const fixtures = [
  {
    name: "software",
    dossier: {
      ...common,
      product_type: "software",
      repository: { provider: "github", full_name: "grinlife4-stack/TRADIX" },
      domain_specification: { runtime: "Node.js", deployment: "not-authorized" }
    }
  },
  {
    name: "physical",
    dossier: {
      ...common,
      product_type: "physical",
      resource_plan: { equipment: ["press", "mould"], raw_materials: ["aluminium"] },
      budget: { currency: "USD", cap: 10000 },
      deliverables: [{ item: "prototype", quantity: 1 }]
    }
  },
  {
    name: "service",
    dossier: {
      ...common,
      product_type: "service",
      resource_plan: { people: ["operator"], capacity: "10 clients" },
      costs: [{ category: "operations", estimate: 500 }],
      risks: [{ id: "R-1", mitigation: "manual review" }]
    }
  },
  {
    name: "hybrid",
    dossier: {
      ...common,
      product_type: "hybrid",
      assets: [{ kind: "hardware", id: "device-1" }, { kind: "software", id: "controller-1" }],
      dependencies: [{ type: "supplier", name: "supplier-a" }]
    }
  }
];

for (const fixture of fixtures) {
  assert.equal(validate(fixture.dossier), true, `${fixture.name}: ${ajv.errorsText(validate.errors)}`);
}
console.log("PASS: software, physical, service, and hybrid product dossier fixtures");

const invalidCases = [
  { ...common, product_type: "physical", schema_version: 2 },
  { ...common, product_type: "physical", mission: "" },
  { ...common, product_type: "physical", requirements: [] },
  { ...common, product_type: "physical", acceptance_criteria: [] },
  { ...common, product_type: "physical", lifecycle: {} },
  { ...common, product_type: "physical", lifecycle: { state: "active", target_date: "31-01-2027" } }
];

for (const invalid of invalidCases) {
  assert.equal(validate(invalid), false, "invalid dossier fixture unexpectedly passed");
}
console.log("PASS: invalid schema version, empty required fields, missing lifecycle state, and malformed dates rejected");

const extensible = {
  ...common,
  product_type: "physical",
  custom_product_domain: { production_line: "line-a", quality_gate: ["dimension", "finish"] }
};
assert.equal(validate(extensible), true, "product-specific extension field was rejected");
console.log("PASS: product-specific extension fields remain supported");
