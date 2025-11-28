from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

doc = SimpleDocTemplate("/mnt/data/OSPF_Final_Report.pdf", pagesize=A4)
styles = getSampleStyleSheet()
story = []

text = """
Open Shortest Path First (OSPF) – Final Report
Student: Nursultan Kaziz
Email: SDU student email
Result: 100% Completion

Objectives
- Configure a multi-area OSPF domain using Backbone, Stub, NSSA, and Secret Area types
- Establish full router adjacency
- Manipulate routing paths using OSPF cost
- Reach Google DNS (8.8.8.8) from R4 and verify reachability

---------------------------------------------------------------
Step-by-Step Configuration Report

1. Initial Router Setup
First of all, I configured each router with hostname and loopback interface matching router ID.
This was repeated for all routers:
R1 1.1.1.1/32
R2 2.2.2.2/32
R3 3.3.3.3/32
R4 4.4.4.4/32
R5 5.5.5.5/32
R7 7.7.7.7/32
R10 10.10.10.10/32

2. OSPF Basic Configuration
Routers were configured with OSPF process 1, router-id set to loopback address and networks placed into correct OSPF areas (Backbone Area 0, Stub Area 1, NSSA Area 2 and Secret area connected through R5).

All Area Border Routers (R10, R1, R2, R3) were assigned networks belonging to area 0 and respective external areas.

3. Secret Area Discovery
R5 was locked, so debug ip ospf adj and debug ip ospf events were used to detect correct area number. The output showed that R5 belongs to Area 1. R2 was configured accordingly and adjacency succeeded.

4. Verify Neighbor Adjacency
Command show ip ospf neighbor confirmed that all routers successfully established OSPF adjacency.

5. OSPF Path Manipulation
To change traffic path, I altered cost on R10->R1 link:
New path: R4 -> R10 -> R2 -> R3 -> R7 -> R8

Additionally, I increased cost on R3->R7 link to 10000 to avoid forwarding through it.

6. Reachability Test
From R4 ping 8.8.8.8 was successful (100% replies)
Traceroute confirmed traffic follows newly optimized path.

---------------------------------------------------------------
Final Result: 100% LAB Completed Successfully

Requirement Status
OSPF Neighbor adjacency ✔
Multi-area (Backbone, Stub, NSSA, Secret) ✔
Default route & Internet reachability ✔
Path manipulation with cost ✔
Ping 8.8.8.8 & traceroute verified ✔

Conclusion
In this lab I configured OSPF areas, resolved adjacency using debugging tools, identified hidden area for R5, and manipulated routing behavior using interface OSPF cost. Final routing confirmed full connectivity to 8.8.8.8 via desired path.
"""

for line in text.split("\n"):
    story.append(Paragraph(line, styles["Normal"]))
    story.append(Spacer(1, 6))

doc.build(story)
"/mnt/data/OSPF_Final_Report.pdf"
