# GPT Escalation Optimization & Usage Dashboard

## Core Pipeline Metrics
- **Total Documents Processed**: 12
- **Total Candidates Scanned**: 1630
- **Total Escalations**: 576
- **Escalation Rate**: 35.34%
- **Average Escalations Per Document**: 48.00
- **Average Cost Per Document**: $0.001141 USD
- **Average Tokens Per Document**: 3584.25
- **Average GPT Response Time**: 14346.42 ms

## Cost Optimization & Reduction Tracking
| Metric | Before | After | Reduction % |
|---|---|---|---|
| Average Escalations | 41.0 | 48.0 | -17.07% |
| Average Tokens | 5750.0 | 3584.2 | 37.67% |
| Average Cost (USD) | $0.0014 | $0.001141 | 18.53% |
| Average Latency | 25.0s | 14.35s | 42.61% |

## Escalation Trigger Statistics
| Trigger Reason | Occurrences | Accuracy/Agreement After GPT |
|---|---|---|
| LOW_CONFIDENCE | 13 | 23.08% |
| CLASSIFIER_CONFLICT | 342 | 25.15% |
| UNKNOWN_PATTERN | 307 | 13.68% |
| HIGH_IMPACT_ACTION | 0 | 0.00% |
| UNIVERSITY_BRANDING_VERIFICATION | 0 | 0.00% |

## Candidate Quality Analytics (Phase 9)

### Pipeline Filtering Summary
- **Total Extracted Candidates**: 978
- **Filtered Out (Low Quality)**: 291
- **Remaining Candidates (Proceeded to Classification)**: 687
- **Candidate Rejection Rate**: 29.75%

### Rejection Reason Breakdown
| Rejection Reason | Count |
|---|---|
| PARAGRAPH_CONTENT | 6 |
| LONG_TEXT | 76 |
| MULTI_SENTENCE | 17 |
| STRUCTURAL_CONTENT | 24 |
| INSTRUCTIONAL_CONTENT | 3 |
| FRAGMENT_CONTENT | 93 |
| REJECTED_PARAGRAPH | 0 |
| REJECTED_LONG_TEXT | 50 |
| REJECTED_MULTI_SENTENCE | 22 |

## Escalation Impact Report (Phase 10)

### Before vs. After Pipeline Performance Comparison
| Metric | Before (Unoptimized) | After (Optimized) | Reduction % |
|---|---|---|---|
| Candidates Proceeding to Classification | 145.0 | 57.2 | 60.52% |
| GPT Escalations | 100.0 | 48.0 | 52.00% |
| Average GPT Cost | $0.0043 | $0.001141 | 73.47% |
| Processing Time (Latency) | 58.0s | 14.35s | 75.26% |

## Token Usage & Cost Telemetry (Phase 10)

- **Average GPT Cost Per Document**: $0.000390 USD
- **Average GPT Cost Per Escalated Candidate**: $0.000019 USD
- **Average Tokens Per Escalated Candidate**: 69.12

### Per-Document Token Telemetry Detail
| Document | Input Tokens | Output Tokens | Cost (USD) | Escalated | Filtered |
|---|---|---|---|---|---|
| doc-123 | 0 | 0 | $0.000000 | 1 | 0 |
| input.docx | 0 | 0 | $0.000000 | 13 | 37 |
| input.pdf | 0 | 0 | $0.000000 | 2 | 0 |
| input.pptx | 0 | 0 | $0.000000 | 4 | 62 |
| 1781777977500_Assessment_Brief_bmp6035_AS1_brief_Jan_2026.docx | 1943 | 1407 | $0.001139 | 67 | 101 |
| 1781778159214_BM561_CW1_Assignment_Brief_2025-26__1_.pdf | 1230 | 315 | $0.000375 | 15 | 2 |
| 1781778231420_Brief_pdf_1382364278.pdf | 4320 | 945 | $0.001215 | 45 | 2 |

## Escalation Source Analysis (Phase 11)

### Global Escalation Trigger Breakdown
| Escalation Trigger | Occurrences | Percentage |
|---|---|---|
| LOW_CONFIDENCE | 7 | 1.42% |
| CLASSIFIER_CONFLICT | 224 | 45.34% |
| UNKNOWN_PATTERN | 263 | 53.24% |
| HIGH_IMPACT_ACTION | 0 | 0.00% |
| UNIVERSITY_BRANDING_VERIFICATION | 0 | 0.00% |

**Dominant Escalation Trigger**: **UNKNOWN_PATTERN** (263 occurrences)

## Automatic Rule Promotion Candidates (Phase 12)

| Candidate | Escalation Count | GPT Classification | Consistency | Recommended Action |
|---|---|---|---|---|
| Academic Year | 4 | `ACADEMIC_TITLE` | 75% | **MONITOR_AND_REVIEW** |
| Artificial Intelligence | 4 | `ACADEMIC_CONTENT` | 100% | **MONITOR_AND_REVIEW** |
| BNU Student Academic Integrity Guidance | 3 | `ACADEMIC_TITLE` | 33% | **MONITOR_AND_REVIEW** |
| Module Lead | 3 | `PERSON` | 33% | **MONITOR_AND_REVIEW** |
| Research Questions | 3 | `ACADEMIC_CONTENT` | 100% | **MONITOR_AND_REVIEW** |
| Generic Grading Criteria | 3 | `ACADEMIC_CONTENT` | 67% | **MONITOR_AND_REVIEW** |
| Mitigating Circumstances | 3 | `PROTECTED_SECTION` | 67% | **MONITOR_AND_REVIEW** |
| Assignment Brief | 2 | `ACADEMIC_TITLE` | 50% | **MONITOR_AND_REVIEW** |
| INCLUDING INTRODUCTION AND CONCLUSIONS | 2 | `ACADEMIC_CONTENT` | 100% | **MONITOR_AND_REVIEW** |
| Additional Information | 2 | `PROTECTED_SECTION` | 50% | **MONITOR_AND_REVIEW** |
| Please DO NOT | 2 | `PROTECTED_SECTION` | 100% | **MONITOR_AND_REVIEW** |
| Research Report | 2 | `ACADEMIC_TITLE` | 50% | **MONITOR_AND_REVIEW** |
| Academic Integrity Guidance | 2 | `ACADEMIC_TITLE` | 50% | **MONITOR_AND_REVIEW** |
| Student Learning | 2 | `ACADEMIC_TITLE` | 50% | **MONITOR_AND_REVIEW** |
| Harvard Referencing | 2 | `ACADEMIC_TITLE` | 50% | **MONITOR_AND_REVIEW** |
| Cite Them Right | 2 | `ACADEMIC_TITLE` | 50% | **MONITOR_AND_REVIEW** |
| Palgrave Macmillan | 2 | `UNIVERSITY_BRANDING` | 100% | **MONITOR_AND_REVIEW** |
| The Cite | 2 | `UNKNOWN` | 50% | **MONITOR_AND_REVIEW** |
| BNU Artificial Intelligence Guidance | 2 | `ACADEMIC_TITLE` | 50% | **MONITOR_AND_REVIEW** |
| Fail | 2 | `ACADEMIC_TITLE` | 50% | **MONITOR_AND_REVIEW** |

## GPT Escalation Diagnostics

### Optimization & Severity Warnings
- **1781774503693_MG414_CW1_Assignment_Brief_1__1_.docx** &rarr; **CRITICAL**: GPT is acting as a primary classifier instead of a fallback classifier.
- **1781778231420_Brief_pdf_1382364278.pdf** &rarr; **HIGH**: Escalation limit exceeded.
- **1781777977500_Assessment_Brief_bmp6035_AS1_brief_Jan_2026.docx** &rarr; **HIGH**: Escalation limit exceeded.
- **1781777977500_Assessment_Brief_bmp6035_AS1_brief_Jan_2026.docx** &rarr; **HIGH**: Escalation volume exceeds optimization target.
- **1781776621275_FMP_Assessment_Brief_Oct_2025_Updated__1___1_.docx** &rarr; **CRITICAL**: GPT is acting as a primary classifier instead of a fallback classifier.

### Phase 3 – Top Escalated Candidates
1. **Academic Year** &rarr; 4 escalations
2. **Artificial Intelligence** &rarr; 4 escalations
3. **BNU Student Academic Integrity Guidance** &rarr; 4 escalations
4. **Module Lead** &rarr; 4 escalations
5. **14:00, 19th June 2026** &rarr; 3 escalations
6. **14:00, 10th July 2026** &rarr; 3 escalations
7. **Fail** &rarr; 3 escalations
8. **Research Questions** &rarr; 3 escalations
9. **Generic Grading Criteria** &rarr; 3 escalations
10. **Mitigating Circumstances** &rarr; 3 escalations
11. **Research Methods** &rarr; 3 escalations
12. **Assignment Brief** &rarr; 2 escalations
13. **INCLUDING INTRODUCTION AND CONCLUSIONS** &rarr; 2 escalations
14. **Additional Information** &rarr; 2 escalations
15. **Please DO NOT** &rarr; 2 escalations
16. **Research Report** &rarr; 2 escalations
17. **Academic Integrity Guidance** &rarr; 2 escalations
18. **Student Learning** &rarr; 2 escalations
19. **Harvard Referencing** &rarr; 2 escalations
20. **Cite Them Right** &rarr; 2 escalations

### Phase 4 – Escalation Reason Breakdown
#### LOW_CONFIDENCE
1. **Umar Gondal** &rarr; 1
2. **Inclusion Services** &rarr; 1
3. **Getting Support** &rarr; 1
4. **Your Assignment** &rarr; 1
5. **Business Consulting** &rarr; 1
6. **Achievement Team** &rarr; 1
7. **John Connor** &rarr; 1
8. **Core Text** &rarr; 1
9. **Principles. Oxford** &rarr; 1
10. **Butterworth-Heinemann** &rarr; 1
11. **Field Theory** &rarr; 1
12. **Social Science** &rarr; 1
13. **Selected Theoretical Papers** &rarr; 1

#### CLASSIFIER_CONFLICT
1. **Academic Year** &rarr; 4
2. **BNU Student Academic Integrity Guidance** &rarr; 4
3. **Module Lead** &rarr; 4
4. **Research Questions** &rarr; 3
5. **Generic Grading Criteria** &rarr; 3
6. **Research Methods** &rarr; 3
7. **Research Report** &rarr; 2
8. **Academic Integrity Guidance** &rarr; 2
9. **Student Learning** &rarr; 2
10. **Harvard Referencing** &rarr; 2
11. **Module leader: Adeeba Ahmad** &rarr; 2
12. **Module lead's name: John Connor** &rarr; 2
13. **Module Lead: Sarah Connor** &rarr; 2
14. **Module code & title:** &rarr; 2
15. **Module leader:** &rarr; 2
16. **Assessment weighting:** &rarr; 2
17. **Submission time and date:** &rarr; 2
18. **Target feedback time and date:** &rarr; 2
19. **Target feedback time and date: ** &rarr; 2
20. **The purpose of this assignment is to apply key theories, models, and principles of organisational behaviour to a real-world business scenario.Task:Imagine that you are working as a Summer Associate during an internship at L.E.K. Consulting based in London, which describes itself as ‘a global strategy consultancy working closely with business leaders to seize competitive advantage and amplify growth’ https://www.lek.com/about-lek.  To get started, your line manager has asked you to provide a report that might be used as marketing material to attract new clients seeking business consultancy services.  You are required to select a business of your choice (make sure it has been approved by the module tutor) and produce a 2,500-word report (+/- 10%) that critically examines the role of culture in driving performance in your chosen organisation. Your analysis should address the following:1. Introduction (200 words)Provide an overview of your chosen organisation, including its background, industry, and business environment.Explain why key factors of organisational culture, motivation and team-work shape workplace behaviour and performance.Organisational Culture, Staff Motivation, and Teamwork (800 words) – LO1Explore the organisation’s culture, focusing on values, norms, and beliefs.Apply relevant cultural, motivational and team-working theories, models, and concepts (e.g., Hofstede’s Cultural Dimensions, Schein’s Organisational Culture Model, Competing Values Framework, Vroom’s Expectancy Theory, Maslow’s Hierarchy of Needs, Herzberg’s Two-Factor Theory  and Belbin’s Team Roles) to explain the cultural framework within the organisation and human behaviour within its teams.Use research to support findings and provide examples illustrating the organisation’s culture.3. Impact on Performance (900 words) – LO2Evaluate how organisational culture, methods of staff motivation and team-working as explained by the theories referred to above, affects performance at the individual, team, and organisational levels. Discuss both positive and negative impacts (e.g., employee motivation, collaboration, efficiency, resistance to change).Reference examples from the organisation to strengthen the analysis.4. Recommendations for Improving Organisational Culture (400 words) – LO3Propose strategies to enhance organisational culture, staff motivation and team-working and improve organisational performance.Justify recommendations by demonstrating an understanding of the link between culture and organisational success. 5. Conclusion (200 words)Summarise key insights from the analysis.Support your analysis with relevant academic literature, including a minimum of 10 references from credible sources such as academic journals, textbooks, and the company’s official website.** &rarr; 2

#### UNKNOWN_PATTERN
1. **Academic Year** &rarr; 4
2. **Artificial Intelligence** &rarr; 4
3. **BNU Student Academic Integrity Guidance** &rarr; 4
4. **14:00, 19th June 2026** &rarr; 3
5. **14:00, 10th July 2026** &rarr; 3
6. **Fail** &rarr; 3
7. **Research Questions** &rarr; 3
8. **Generic Grading Criteria** &rarr; 3
9. **Mitigating Circumstances** &rarr; 3
10. **Assignment Brief** &rarr; 2
11. **INCLUDING INTRODUCTION AND CONCLUSIONS** &rarr; 2
12. **Additional Information** &rarr; 2
13. **Please DO NOT** &rarr; 2
14. **Academic Integrity Guidance** &rarr; 2
15. **Student Learning** &rarr; 2
16. **Harvard Referencing** &rarr; 2
17. **Cite Them Right** &rarr; 2
18. **Palgrave Macmillan** &rarr; 2
19. **The Cite** &rarr; 2
20. **BNU Artificial Intelligence Guidance** &rarr; 2

#### HIGH_IMPACT_ACTION
*No candidates escalated for this reason.*

#### UNIVERSITY_BRANDING_VERIFICATION
*No candidates escalated for this reason.*

### Phase 5 – Low Confidence Investigation
**Average Python Confidence Score per Class (on LOW_CONFIDENCE escalations):**
- **PERSON**: 51.5% confidence

### Phase 6 – Classifier Conflict Investigation
**Conflicting Classifiers:**
1. **PERSON vs ACADEMIC_TITLE** &rarr; 248 occurrences
2. **ACADEMIC_TITLE vs UNKNOWN** &rarr; 82 occurrences
3. **BUSINESS_FIELD vs UNKNOWN** &rarr; 7 occurrences
4. **PROTECTED_SECTION vs UNKNOWN** &rarr; 5 occurrences

### Phase 7 – GPT Agreement Analysis
**Python to GPT Prediction Transitions:**
1. **ACADEMIC_TITLE → ACADEMIC_CONTENT** &rarr; 154 occurrences
2. **UNKNOWN → ACADEMIC_CONTENT** &rarr; 111 occurrences
3. **ACADEMIC_TITLE → ACADEMIC_TITLE** &rarr; 73 occurrences
4. **UNKNOWN → ACADEMIC_TITLE** &rarr; 40 occurrences
5. **PERSON → PERSON** &rarr; 11 occurrences
6. **PERSON → ACADEMIC_CONTENT** &rarr; 10 occurrences
7. **ACADEMIC_TITLE → PROTECTED_SECTION** &rarr; 8 occurrences
8. **UNKNOWN → PROTECTED_SECTION** &rarr; 7 occurrences
9. **PROTECTED_SECTION → PROTECTED_SECTION** &rarr; 6 occurrences
10. **UNKNOWN → PERSON** &rarr; 5 occurrences
11. **PERSON → ACADEMIC_TITLE** &rarr; 4 occurrences
12. **BUSINESS_FIELD → ACADEMIC_TITLE** &rarr; 4 occurrences
13. **UNKNOWN → SUBMISSION_EVENT** &rarr; 4 occurrences
14. **UNKNOWN → UNIVERSITY_BRANDING** &rarr; 3 occurrences
15. **BUSINESS_FIELD → PROTECTED_SECTION** &rarr; 3 occurrences
16. **BUSINESS_FIELD → SUBMISSION_EVENT** &rarr; 3 occurrences
17. **SECTION_HEADING → ACADEMIC_TITLE** &rarr; 2 occurrences
18. **BUSINESS_FIELD → ACADEMIC_CONTENT** &rarr; 2 occurrences
19. **UNKNOWN → UNKNOWN** &rarr; 1 occurrences
20. **ACADEMIC_TITLE → SUBMISSION_EVENT** &rarr; 1 occurrences
21. **PERSON → SUBMISSION_EVENT** &rarr; 1 occurrences
22. **ACADEMIC_TITLE → UNIVERSITY_BRANDING** &rarr; 1 occurrences
23. **SUBMISSION_EVENT → SUBMISSION_EVENT** &rarr; 1 occurrences
24. **SECTION_HEADING → ACADEMIC_CONTENT** &rarr; 1 occurrences

### Phase 8 – Escalation Reduction Opportunities
1. **Academic Year** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 75.0%, Conf: 100.0%, Docs: 4, Occurrences: 4]
   * Recommended Action: **KEEP_GPT_ESCALATION**
2. **Artificial Intelligence** &rarr; recommend classification: `ACADEMIC_CONTENT`
   * [Consistency: 100.0%, Conf: 100.0%, Docs: 3, Occurrences: 4]
   * Recommended Action: **KEEP_GPT_ESCALATION**
3. **BNU Student Academic Integrity Guidance** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 33.3%, Conf: 100.0%, Docs: 4, Occurrences: 3]
   * Recommended Action: **KEEP_GPT_ESCALATION**
4. **Module Lead** &rarr; recommend classification: `PERSON`
   * [Consistency: 33.3%, Conf: 100.0%, Docs: 3, Occurrences: 3]
   * Recommended Action: **KEEP_GPT_ESCALATION**
5. **Research Questions** &rarr; recommend classification: `ACADEMIC_CONTENT`
   * [Consistency: 100.0%, Conf: 100.0%, Docs: 1, Occurrences: 3]
   * Recommended Action: **KEEP_GPT_ESCALATION**
6. **Generic Grading Criteria** &rarr; recommend classification: `ACADEMIC_CONTENT`
   * [Consistency: 66.7%, Conf: 100.0%, Docs: 2, Occurrences: 3]
   * Recommended Action: **KEEP_GPT_ESCALATION**
7. **Mitigating Circumstances** &rarr; recommend classification: `PROTECTED_SECTION`
   * [Consistency: 66.7%, Conf: 100.0%, Docs: 2, Occurrences: 3]
   * Recommended Action: **KEEP_GPT_ESCALATION**
8. **Assignment Brief** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
9. **INCLUDING INTRODUCTION AND CONCLUSIONS** &rarr; recommend classification: `ACADEMIC_CONTENT`
   * [Consistency: 100.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
10. **Additional Information** &rarr; recommend classification: `PROTECTED_SECTION`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
11. **Please DO NOT** &rarr; recommend classification: `PROTECTED_SECTION`
   * [Consistency: 100.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
12. **Research Report** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
13. **Academic Integrity Guidance** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
14. **Student Learning** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
15. **Harvard Referencing** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
16. **Cite Them Right** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
17. **Palgrave Macmillan** &rarr; recommend classification: `UNIVERSITY_BRANDING`
   * [Consistency: 100.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
18. **The Cite** &rarr; recommend classification: `UNKNOWN`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
19. **BNU Artificial Intelligence Guidance** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 2, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**
20. **Fail** &rarr; recommend classification: `ACADEMIC_TITLE`
   * [Consistency: 50.0%, Conf: 100.0%, Docs: 3, Occurrences: 2]
   * Recommended Action: **KEEP_GPT_ESCALATION**

### Most Expensive Documents
1. 1781776621275_FMP_Assessment_Brief_Oct_2025_Updated__1___1_.docx &rarr; $0.004509 USD
2. 1781775332396_MG414_CW1_Assignment_Brief_1__1_.docx &rarr; $0.004300 USD
3. 1781773552743_brief_pdf_1037313543_original.pdf &rarr; $0.001435 USD
4. 1781778231420_Brief_pdf_1382364278.pdf &rarr; $0.001215 USD
5. 1781777977500_Assessment_Brief_bmp6035_AS1_brief_Jan_2026.docx &rarr; $0.001139 USD
6. 1781772924236_BM561_CW1_Assignment_Brief_2025-26.pdf &rarr; $0.000714 USD
7. 1781778159214_BM561_CW1_Assignment_Brief_2025-26__1_.pdf &rarr; $0.000375 USD
8. input.pptx &rarr; $0.000000 USD
9. 1781774503693_MG414_CW1_Assignment_Brief_1__1_.docx &rarr; $0.000000 USD
10. doc-123 &rarr; $0.000000 USD

### Highest Escalation Documents
1. 1781776621275_FMP_Assessment_Brief_Oct_2025_Updated__1___1_.docx &rarr; 167 escalations
2. 1781774503693_MG414_CW1_Assignment_Brief_1__1_.docx &rarr; 100 escalations
3. 1781775332396_MG414_CW1_Assignment_Brief_1__1_.docx &rarr; 100 escalations
4. 1781777977500_Assessment_Brief_bmp6035_AS1_brief_Jan_2026.docx &rarr; 67 escalations
5. 1781778231420_Brief_pdf_1382364278.pdf &rarr; 45 escalations
6. 1781773552743_brief_pdf_1037313543_original.pdf &rarr; 41 escalations
7. 1781772924236_BM561_CW1_Assignment_Brief_2025-26.pdf &rarr; 21 escalations
8. 1781778159214_BM561_CW1_Assignment_Brief_2025-26__1_.pdf &rarr; 15 escalations
9. input.docx &rarr; 13 escalations
10. input.pptx &rarr; 4 escalations
