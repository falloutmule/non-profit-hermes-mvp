# Board API verification

VERIFIED production df7e07daad874a16cf69522c77b6fa5269b91051, schema migration 3. Hermes uses existing loopback bearer boundary, no SQL tools. Authenticated event list, event detail, staffing, projection snapshot/pending and series adoption passed. Twelve event IDs/times/status/capacity preserved. Existing private operational rows internally compared equal to preupgrade backup; no row values exported. /health and /ready local/public HTTP200.

Writes verified in isolated fixtures; live writes limited to legitimate recurrence adoption and projection acknowledgement. No SMS, invitation, publication or synthetic volunteer writes.
