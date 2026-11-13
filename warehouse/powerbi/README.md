# Power BI Desktop (Snowflake source)
1. Open Power BI Desktop → Get Data → Snowflake.
2. Server: your Snowflake account hostname (from Snowsight), Warehouse: WATER_LEAK_COMPUTE.
3. Select database WATER_LEAK_WH and schema ANALYTICS.
4. Choose **Import** for a student/demo report (refresh manually). Select reporting views:
   - V_CASE_EVALUATION
   - V_ZONE_PERFORMANCE
   - V_REPAIR_TRENDS
5. Report pages:
   - Detection quality: confirmed, false alarms, unverified (separate categories)
   - Zone comparison: suspected and confirmed cases by zone
   - Risk transparency: case ID + score + status + model version
   - Repairs over time: monthly confirmed and no-leak inspections
6. DAX measures on V_CASE_EVALUATION:

```dax
Suspected Cases = COUNTROWS(V_CASE_EVALUATION)
Confirmed Leaks = CALCULATE(COUNTROWS(V_CASE_EVALUATION), V_CASE_EVALUATION[EVALUATION_STATUS] = "CONFIRMED")
False Alarms = CALCULATE(COUNTROWS(V_CASE_EVALUATION), V_CASE_EVALUATION[EVALUATION_STATUS] = "FALSE_ALARM")
Verified Cases = [Confirmed Leaks] + [False Alarms]
Confirmation Rate = DIVIDE([Confirmed Leaks], [Verified Cases])
Unverified Cases = CALCULATE(COUNTROWS(V_CASE_EVALUATION), V_CASE_EVALUATION[EVALUATION_STATUS] = "NOT_YET_VERIFIED")
```

Important: Confirmation rate is calculated ONLY among conclusive inspected cases. It is not recall, and neither confirmed percentage nor estimated water loss is ground truth for uninspected cases.
