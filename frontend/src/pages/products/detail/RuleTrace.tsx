import CancelOutlined from '@mui/icons-material/CancelOutlined';
import CheckCircle from '@mui/icons-material/CheckCircle';
import Box from '@mui/material/Box';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';

import type { RiskDetail } from '../../../api/types';
import RiskBadge from '../../../components/RiskBadge';

export const DETERMINISTIC_LABEL = 'Deterministic rule evaluation — not AI';

/** Plain-language BP §7.4 rules (first matching rule wins). Display text only. */
export const RULE_DESCRIPTIONS: Record<string, string> = {
  R1: 'Available stock is zero or less while there is recent demand (ADS30 > 0).',
  R2: 'There is recent demand and the projected stock reaches zero within the lead time (BP 7.3).',
  R3: 'Inventory position is at or below the reorder point.',
  R4: 'Days of cover is below the lead time plus the review period.',
  R5: 'Days of cover is above the overstock threshold, or there is stock on hand with no recent demand.',
  R6: 'None of the rules above matched: stock is healthy.',
};

/**
 * Section 4 body: the rules checked in order, as the API returns them (it stops at the rule that
 * fired, so later rules never appear). The fired rule is highlighted with its reason code.
 */
export default function RuleTrace({ risk }: { risk: RiskDetail }) {
  const theme = useTheme();
  const trace = risk.rule_trace;
  return (
    <Box>
      <Typography variant="overline" component="p" color="text.secondary">
        {DETERMINISTIC_LABEL}
      </Typography>
      <Box component="ol" aria-label="Rules checked" sx={{ listStyle: 'none', m: 0, p: 0 }}>
        {trace.rules_checked.map((check) => {
          const fired = check.rule === trace.rule_fired;
          return (
            <Box
              component="li"
              key={check.rule}
              data-fired={fired || undefined}
              sx={{
                display: 'grid',
                gridTemplateColumns: 'auto auto 1fr',
                alignItems: 'center',
                gap: 1.5,
                p: 1,
                mb: 0.5,
                borderRadius: 1,
                border: 1,
                borderColor: fired ? theme.palette.text.primary : 'transparent',
                borderWidth: fired ? 2 : 1,
                bgcolor: fired ? theme.palette.background.paper : 'transparent',
              }}
            >
              {check.matched ? (
                <CheckCircle titleAccess="matched" sx={{ color: theme.palette.success.main }} />
              ) : (
                <CancelOutlined
                  titleAccess="not matched"
                  sx={{ color: theme.palette.text.secondary }}
                />
              )}
              <Typography sx={{ fontFamily: 'monospace', fontWeight: 700 }}>
                {check.rule}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                <RiskBadge risk={check.class} />
                <Typography variant="body2" color="text.secondary">
                  {check.matched ? 'Matched' : 'Not matched'}
                </Typography>
                {fired ? (
                  <Box sx={{ flexBasis: '100%' }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      Fired:{' '}
                      <Box component="code" data-testid="reason-code">
                        {trace.reason_code}
                      </Box>
                    </Typography>
                    <Typography variant="body2">{RULE_DESCRIPTIONS[check.rule] ?? ''}</Typography>
                  </Box>
                ) : null}
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}
