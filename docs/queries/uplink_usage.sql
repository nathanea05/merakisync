-- Uplink usage per WAN interface per month, with network name.
-- Bytes stored in the DB are converted to gigabytes (1 GB = 1,073,741,824 bytes).
SELECT
    n.name                                              AS network_name,
    u.interface                                         AS wan_interface,
    u.year,
    u.month,
    ROUND(u.sent     / 1073741824.0, 2)                 AS sent_gb,
    ROUND(u.received / 1073741824.0, 2)                 AS received_gb,
    ROUND((u.sent + u.received) / 1073741824.0, 2)      AS total_gb
FROM meraki.uplink_usage u
JOIN meraki.network n
    ON n.id = u.network_id
   AND n.active_to IS NULL
ORDER BY
    u.year  DESC,
    u.month DESC,
    n.name,
    u.interface;
