# things learned

The main thing that jumps out is Chunk 54:

Chunk 54: 17,466 characters
Section: UNIT PRICE TABLE

That's your giant pricing table. You already extracted that separately as a DataFrame/CSV, so I would not further text-chunk that table. I would remove that chunk from the Markdown chunks and use your structured table version instead.



There is one weakness in our current reducer logic that we'll want to fix: a category can contain both direct requirements and external references.

For example, bonding_security could have a direct bid-security requirement plus a referenced external bond form. In that case, a single category-level status loses some information.

I wouldn't stop the build for that yet. Once we add the table workers, I'd improve the final schema so individual requirements retain their own statuses, while the category acts as a grouping layer.


One small improvement: for now, I would process every Docling table. We can later add a cheap table-classification step if we discover many tables are useless.


There is one issue I would expect when you run this: the 17,466-character Unit Price Table may also be large when converted from its DataFrame to Markdown. That's okay for the first test, but if the DataFrame is very large, the proper next improvement is to map table rows or logical groups of rows, rather than treating an enormous table as one LLM request.

The speaker wants to do this:Chunking / Mapping:Send Prompt + Rows 1 to 50 ➔ LLM ➔ Processed Output Part 1Send Prompt + Rows 51 to 100 ➔ LLM ➔ Processed Output Part 2Send Prompt + Rows 101 to 150 ➔ LLM ➔ Processed Output Part 3The Result: The system loops through the table in manageable batches (logical groups), processes each batch independently, and combines the results at the end.




Yes. Comparing the text-only result with the text + table result, I think adding the table workers was the right move. The second result is materially better, especially for the technical and financial parts of the tender.

The clearest improvement is Technical. Text-only mostly found the construction duration and some referenced requirements. Once tables were included, the agent picked up the actual scope of work: excavation, paving, catch basins, asphalt, curbs, sidewalks, storm sewer pipe, retaining walls, street lights, quantities, units, and specification references. That's exactly the kind of information a bid/no-bid system needs.

Financial also improved. Text-only found the total bid amount and some tax/payment provisions. With tables, it correctly identified that bidders need prices for every listed item, that unit prices govern the extended amount, arithmetic corrections can occur, and prices can be assessed for reasonableness.

Submission also got a useful addition from the tables:

"Provide pricing for each listed item and transfer the total estimated amount..."

That wasn't as explicit in the text-only result



did we have a problem with tables taht are useless

Yes. We identified that issue earlier.

Docling extracted all the tables, but not every table was useful for requirement extraction. Some are just document-layout tables, header information, addresses, metadata, or other content that doesn't establish a tender requirement.

Right now, we handle that mainly through the table Map worker prompt:

If the table contains no relevant requirements,
return an empty list.


did we deduplicate and if so where

Yes. Deduplication is happening in your reduce_findings node, not in the Map workers.
Specifically, it's happening because of these instructions in your reducer prompt:

CONSOLIDATION RULES:

- Combine duplicate findings.
- Combine evidence from text and tables when they describe the
  same requirement.

So right now, the LLM reducer is doing semantic deduplication.


Yes. We fixed that weakness.

Originally, your reducer put one status on the entire category:

BONDING_SECURITY
Status: EXTERNAL_REFERENCE

That was a problem because a category can contain both:

Bid security must be enclosed
→ FOUND

Details/amount are defined in GI09
→ EXTERNAL_REFERENCE




did we handle that weakness in our reduer logic that was taht a category can contain both direct requirements and external references.

Yes. We fixed that weakness.

Originally, your reducer put one status on the entire category:

BONDING_SECURITY
Status: EXTERNAL_REFERENCE

That was a problem because a category can contain both:

Bid security must be enclosed
→ FOUND

Details/amount are defined in GI09
→ EXTERNAL_REFERENCE

We fixed it by moving the meaningful status down to each individual requirement: