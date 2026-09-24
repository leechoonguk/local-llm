/**
 * What the Food Code says about the product, laid out the way the Code is.
 *
 * Not a table: a clause is five different things - what is measured, under
 * what condition, the value that decides, how it is judged, and the Code's
 * own sentence - and a row that folded them into one clipped cell lost the
 * condition and the judgement first. So every clause prints whole, wrapped,
 * and the clauses stand under the Code's outline heading they hang on, in
 * outline order (the heading codes are assigned in it), with the prefix every
 * heading shares printed once. A heading with more than `FOLD_OVER` clauses
 * starts folded - 발기부전치료제 lists 55 - the rest open, because reading
 * them is the point.
 *
 * A tab is a pure presenter: the dialog fetched the standards when this tab
 * opened and hands them here. No paging - an outline is read, not browsed -
 * so the dialog owns nothing of this tab but the query.
 */

import { Fragment, useState } from 'react'
import { Alert, Box, Button, Collapse, Stack, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import DetailSection from '@/components/detail/DetailSection'
import { RECORD_SURFACE } from '@/config'
import Iconify from '@/components/iconify/Iconify'
import Label from '@/components/label/Label'
import type {
  FoodItemReportCommonStandard,
  FoodItemReportHeading,
  FoodItemReportStandardClause,
  FoodItemReportTypeStandards,
} from '@/types/food'

/** A heading with this many clauses or more starts folded. */
const FOLD_OVER = 20

/** The Code's outline levels every heading shares are shown once above the groups. */
interface HeadingGroup {
  key: string
  /** The heading path below the shared prefix, top first. */
  path: FoodItemReportHeading[]
  rows: FoodItemReportCommonStandard[]
}

export default function FoodItemReportStandardsTab({ types }: { types: FoodItemReportTypeStandards[] }) {
  const { t } = useTranslation('food')

  if (types.length === 0) {
    return <Alert severity="warning">{t('item_report.standards.no_type')}</Alert>
  }

  return (
    <Stack spacing={RECORD_SURFACE.SECTION_GROUP_GAP}>
      {types.map((entry) => (
        <TypeOutline key={entry.node.product_code} entry={entry} />
      ))}
    </Stack>
  )
}

function TypeOutline({ entry }: { entry: FoodItemReportTypeStandards }) {
  const { t } = useTranslation('food')
  const prefix = sharedPrefix(entry.common_standards)
  const groups = groupByHeading(entry.common_standards, prefix.length)
  const [folded, setFolded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(groups.map((g) => [g.key, g.rows.length >= FOLD_OVER])),
  )
  const allFolded = groups.every((g) => folded[g.key])
  const toggleAll = () => setFolded(Object.fromEntries(groups.map((g) => [g.key, !allFolded])))

  return (
    <Stack spacing={RECORD_SURFACE.SECTION_GAP}>
      <DetailSection
        name="link"
        title={`${entry.node.korean_name ?? entry.node.product_code} · ${entry.node.product_code}`}
      >
        <Typography variant="body2" color="text.secondary">
          {entry.path.map((node, index) => (
            <Fragment key={node.product_code}>
              {index > 0 && ' › '}
              {node.korean_name ?? node.product_code}
            </Fragment>
          ))}
        </Typography>
      </DetailSection>

      <DetailSection
        name="shield"
        title={t('item_report.standards.individual_count', { clauses: String(entry.individual_standards.length) })}
      >
        {entry.individual_standards.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t('item_report.standards.none_individual')}
          </Typography>
        ) : (
          <Stack spacing={1.5}>
            {entry.individual_standards.map((clause) => (
              <ClauseLine key={clause.id} clause={clause} />
            ))}
          </Stack>
        )}
      </DetailSection>

      <DetailSection
        name="layers"
        title={t('item_report.standards.common_count', {
          clauses: String(entry.common_standards.length),
          headings: String(groups.length),
        })}
        action={
          groups.length > 0 ? (
            <Button
              size="small"
              startIcon={<Iconify name={allFolded ? 'expand' : 'collapse'} />}
              onClick={toggleAll}
            >
              {allFolded ? t('item_report.standards.expand_all') : t('item_report.standards.fold_all')}
            </Button>
          ) : undefined
        }
      >
        {prefix.length > 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
            {prefix.map((h) => h.standard_name ?? h.common_standard_type_code).join(' › ')}
          </Typography>
        )}
        <Stack spacing={1}>
          {groups.map((group) => (
            <Box key={group.key} sx={{ borderTop: 1, borderColor: 'divider', pt: 1 }}>
              <Stack
                direction="row"
                alignItems="center"
                spacing={1}
                sx={{ cursor: 'pointer' }}
                onClick={() => setFolded((current) => ({ ...current, [group.key]: !current[group.key] }))}
              >
                <Iconify name={folded[group.key] ? 'expand' : 'collapse'} />
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>
                  {group.path.map((h) => h.standard_name ?? h.common_standard_type_code).join(' › ')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('item_report.standards.clause_count', { clauses: String(group.rows.length) })}
                </Typography>
                {uniqueSources(group.rows).map((source) => (
                  <Label key={source} variant="soft" color="default">
                    {source}
                  </Label>
                ))}
              </Stack>
              <Collapse in={!folded[group.key]} unmountOnExit>
                <Stack spacing={1.5} sx={{ pl: 4, py: 1.5 }}>
                  {group.rows.map((row) => (
                    <ClauseLine key={row.standard.id} clause={row.standard} />
                  ))}
                </Stack>
              </Collapse>
            </Box>
          ))}
        </Stack>
      </DetailSection>
    </Stack>
  )
}

/** One clause, whole: what · under what condition · the deciding value · how judged, then the Code's sentence. */
function ClauseLine({ clause }: { clause: FoodItemReportStandardClause }) {
  const { t } = useTranslation('food')
  const condition = clause.clause_name || clause.detail_item_name
  const value = decidingValue(clause)
  return (
    <Box>
      <Stack direction="row" alignItems="center" spacing={1} flexWrap="wrap" useFlexGap>
        <Typography variant="subtitle2">{clause.test_item_name ?? clause.test_item_code}</Typography>
        {condition && (
          <Typography variant="body2" color="text.secondary">
            ⟨{condition}⟩
          </Typography>
        )}
        {value !== null && (
          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
            {value}
            {clause.unit_name ? ` ${clause.unit_name}` : ''}
          </Typography>
        )}
        {clause.judgment_format_name && (
          <Label variant="soft" color="info">
            {clause.judgment_format_name}
          </Label>
        )}
        {clause.hazard_yn === 'Y' && (
          <Label variant="soft" color="error">
            {t('item_report.standards.hazard')}
          </Label>
        )}
      </Stack>
      {clause.standard_value_summary && clause.standard_value_summary !== value && (
        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', mt: 0.25 }}>
          {clause.standard_value_summary}
        </Typography>
      )}
    </Box>
  )
}

/** The value that decides - the Code's short form, or the bounds when only those are given. */
function decidingValue(clause: FoodItemReportStandardClause): string | null {
  if (clause.standard_value !== null) return clause.standard_value
  const bounds = [clause.minimum_value, clause.maximum_value].filter((v) => v !== null)
  return bounds.length === 0 ? null : bounds.join(' ~ ')
}

/** The outline levels every clause's heading path starts with. */
function sharedPrefix(rows: FoodItemReportCommonStandard[]): FoodItemReportHeading[] {
  if (rows.length === 0) return []
  let prefix = rows[0].heading_path
  for (const row of rows) {
    let n = 0
    while (
      n < prefix.length &&
      n < row.heading_path.length &&
      prefix[n].common_standard_type_code === row.heading_path[n].common_standard_type_code
    ) {
      n += 1
    }
    prefix = prefix.slice(0, n)
  }
  // A path that is exactly the prefix would have nothing left to name its group by.
  const shortest = Math.min(...rows.map((row) => row.heading_path.length))
  return prefix.slice(0, Math.max(0, Math.min(prefix.length, shortest - 1)))
}

/** Clauses under their leaf heading, in the Code's order - the heading codes are assigned in it. */
function groupByHeading(rows: FoodItemReportCommonStandard[], prefixLength: number): HeadingGroup[] {
  const groups = new Map<string, HeadingGroup>()
  for (const row of rows) {
    const key = row.heading_path.map((h) => h.common_standard_type_code).join('/') || '-'
    const group = groups.get(key) ?? { key, path: row.heading_path.slice(prefixLength), rows: [] }
    group.rows.push(row)
    groups.set(key, group)
  }
  return [...groups.values()].sort((a, b) => a.key.localeCompare(b.key))
}

function uniqueSources(rows: FoodItemReportCommonStandard[]): string[] {
  return [...new Set(rows.map((row) => row.inherited_from.korean_name ?? row.inherited_from.product_code))]
}
