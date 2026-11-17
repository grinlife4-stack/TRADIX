# Provider adapter contract

Every connector is an independently replaceable adapter. It must declare:
- provider and API version;
- official documentation and permitted use;
- required scopes and credential handling;
- supported countries, currencies and rate limits;
- source timestamp, retrieval timestamp and provenance for every observation;
- whether the data represents sales, rank, estimates, offers or advertisements;
- supplier identity and a separate written dropship authorization record;
- fulfillment countries, delivery SLA, tracking, returns and packaging terms.

A provider's product API, affiliate program or public catalog does not itself grant wholesale resale or direct-fulfillment rights. Do not infer dropshipping support from a product listing.

Adapters must return normalized records and must not place orders, publish listings, charge customers or transfer money. Those are separate capabilities behind explicit policy and approval gates.

## Initial provider strategy
1. Alibaba supplier-side discovery: investigate official partner/API access and supplier-level written terms.
2. Amazon: treat as a demand/market signal only where authorized. Do not assume Amazon retail orders can be forwarded to customers as a compliant supply route.
3. eBay: wholesale supplier agreements only; buying from another retailer/marketplace after a sale is not an acceptable fulfillment strategy under eBay policy.
4. Additional supplier networks: evaluate official dropship APIs and contractual fulfillment support before enabling.

No connector is enabled in v0.1.
