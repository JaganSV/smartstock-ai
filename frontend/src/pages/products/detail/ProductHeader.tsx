import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import type { ProductDetail } from '../../../api/types';
import RiskBadge from '../../../components/RiskBadge';
import VerifiedDataPanel from '../../../components/VerifiedDataPanel';
import { formatDate, formatDateTime, formatMoney, formatNumber } from '../../../lib/format';
import KeyValueList from './KeyValueList';

/** Section 1: who the product is, its supplier terms and its roll-up class (FR-C2). */
export default function ProductHeader({ detail }: { detail: ProductDetail }) {
  const { product, rollup, snapshot } = detail;
  return (
    <Box sx={{ display: 'grid', gap: 1.5 }}>
      <Box>
        <Typography variant="h1">
          {product.sku} · {product.name}
        </Typography>
        <Typography variant="body2" color="text.secondary" data-testid="snapshot-line">
          Verified · calculated {formatDateTime(snapshot.calculated_at)} · data as of{' '}
          {formatDate(snapshot.data_as_of_date)}
        </Typography>
      </Box>
      <VerifiedDataPanel
        title="Product"
        snapshot={snapshot}
        actions={
          rollup ? (
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }} data-testid="rollup">
              <RiskBadge risk={rollup.risk_class} />
              <Typography variant="body2">driven by {rollup.risk_warehouse_code}</Typography>
              {rollup.is_dead_stock ? (
                <Chip label="Dead stock" size="small" color="error" variant="outlined" />
              ) : null}
            </Stack>
          ) : null
        }
      >
        <KeyValueList
          label="Product facts"
          items={[
            { label: 'Category', value: product.category.name },
            { label: 'Supplier', value: `${product.supplier.name} (${product.supplier.code})` },
            {
              label: 'Supplier lead time',
              value: `${formatNumber(product.supplier.default_lead_time_days)} days`,
            },
            { label: 'Minimum order qty', value: formatNumber(product.supplier.min_order_qty) },
            { label: 'Unit cost', value: formatMoney(product.unit_cost) },
            { label: 'Unit price', value: formatMoney(product.unit_price) },
            { label: 'Case pack', value: formatNumber(product.case_pack) },
          ]}
        />
      </VerifiedDataPanel>
    </Box>
  );
}
