import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.tools import (
    trace_pep_lineage, get_foundational_non_current_peps, get_author_influence,
    get_coauthor_bridges, get_rejected_peps_cited_later, get_high_rejection_authors_still_cited,
    get_unreferenced_peps, get_rejection_reasons, get_replacement_similarity,
    get_unlinked_similar_peps, get_resurfaced_rejected_ideas, get_delegates_of_superseded_peps,
    get_peps_by_release, search_peps, get_pep_details, get_pep_sections,
    traverse_graph, find_shortest_path, check_relationship_absence,
    execute_guarded_cypher
)

print("1. trace_pep_lineage(566):")
r1 = trace_pep_lineage(566)
print("   Chains:", r1["maximal_chains"])

print("2. get_foundational_non_current_peps(25):")
r2 = get_foundational_non_current_peps(25)
print("   Non-current:", [p["number"] for p in r2["non_current_peps"]])

print("3. search_peps('pattern matching'):")
r3 = search_peps("pattern matching", top_k=2)
print("   Matches:", [(m["number"], m["title"]) for m in r3["results"]])

print("4. get_pep_details(572):")
r4 = get_pep_details(572)
print("   Title:", r4["pep"]["title"], "Status:", r4["pep"]["status"], "Authors:", r4["pep"]["authors"])

print("5. find_shortest_path(484, 3107):")
r5 = find_shortest_path(484, 3107)
print("   Route:", r5["route"], "Hops:", r5["hops"])

print("6. check_relationship_absence(332, 358, ['CITES']):")
r6 = check_relationship_absence(332, 358, ["CITES"])
print("   Absence proven:", r6["absence_proven"])

print("7. execute_guarded_cypher mutation test:")
r7_bad = execute_guarded_cypher("MATCH (p:PEP) DELETE p")
print("   Mutation blocked:", "error" in r7_bad)

r7_good = execute_guarded_cypher("MATCH (p:PEP {number: 566}) RETURN p.title")
print("   Read query result:", r7_good["rows"])
