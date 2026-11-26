import Box from '@mui/material/Box';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';

import type { WarehouseMetric } from '../../../api/types';
import RiskBadge from '../../../components/RiskBadge';

interface Props {
  warehouses: WarehouseMetric[];
  selected: number;
  onChange: (warehouseId: number) => void;
}

/** Section 2: one tab per warehouse, each with its class as a small badge. */
export default function WarehouseTabs({ warehouses, selected, onChange }: Props) {
  return (
    <Tabs
      value={selected}
      onChange={(_, value: number) => onChange(value)}
      aria-label="Warehouse"
      variant="scrollable"
      allowScrollButtonsMobile
    >
      {warehouses.map((row) => (
        <Tab
          key={row.warehouse_id}
          value={row.warehouse_id}
          label={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {row.warehouse_code}
              <RiskBadge risk={row.risk_class} />
            </Box>
          }
          aria-label={`${row.warehouse_code}, risk ${row.risk_class}`}
        />
      ))}
    </Tabs>
  );
}
