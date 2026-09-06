/**
 * One provider, read and edited inside one dialog.
 *
 * The stack is provider dialog → panel, never provider dialog → second modal: a
 * confirm dialog on top of this one hides the record it is asking about, and a
 * third layer over a form the user is still filling has nowhere to go back to.
 * So a panel *replaces* the body while the provider header stays on screen, and
 * "back" is a button in the panel's pinned strip.
 *
 * The dialog owns three pieces of state because all three have the same lifetime
 * as the dialog itself: which tab is showing, which panel replaced the body, and
 * where each table is paged to. Paging in particular cannot live in the tab —
 * opening a record unmounts it, and the reader would return from the record they
 * just edited to page 1 (measured: deleting the last credential on page 2 of 12
 * landed back on `1–10`).
 */

import { useState } from 'react'
import {
  Box,
  CircularProgress,
  Dialog,
  DialogContent,
  IconButton,
  Stack,
  Tab,
  Tabs,
  Typography,
} from '@mui/material'
import { useTranslation } from 'react-i18next'
import Iconify from '@/components/iconify/Iconify'
import type { ActionIcon } from '@/components/iconify/icons'
import Label from '@/components/label/Label'
import { RECORD_SURFACE } from '@/config'
import { useIntegration } from '@/lib/api/hooks/useIntegration'
import { useQueryErrorToast } from '@/hooks/useQueryErrorToast'
import { useTablePage } from '@/hooks/useTablePage'
import IntegrationOperationDeletePanel from '@/sections/integration/IntegrationOperationDeletePanel'
import IntegrationOperationPanel from '@/sections/integration/IntegrationOperationPanel'
import IntegrationRunPanel from '@/sections/integration/IntegrationRunPanel'
import IntegrationSecretDeletePanel from '@/sections/integration/IntegrationSecretDeletePanel'
import IntegrationSecretPanel from '@/sections/integration/IntegrationSecretPanel'
import IntegrationOperationsTab from '@/sections/integration/detail/IntegrationOperationsTab'
import IntegrationSecretsTab from '@/sections/integration/detail/IntegrationSecretsTab'
import { formatDateTime } from '@/utils/formatTime'
import type { IntegrationOperation, IntegrationSecret } from '@/types/integration'

type DetailTab = 'operations' | 'secrets'

/**
 * What the dialog body shows: the tabs, or the one panel that replaced them.
 *
 * A record is addressed by the key the server keeps unique — an operation by its
 * `code`, a credential by its `name` — never by the object: `PUT /integration/{id}`
 * replaces the whole operations array, so a held object is a stale row with a new
 * id behind it.
 */
type PanelMode =
  | { kind: 'tabs' }
  | { kind: 'operation'; operationCode: string }
  | { kind: 'create' }
  | { kind: 'run'; operation: IntegrationOperation }
  | { kind: 'delete'; operation: IntegrationOperation }
  | { kind: 'secret'; secretName: string }
  | { kind: 'secretCreate' }
  | { kind: 'secretDelete'; secret: IntegrationSecret }

const TAB_ICONS: Record<DetailTab, ActionIcon> = {
  operations: 'link',
  secrets: 'lock',
}

const TAB_ORDER: DetailTab[] = ['operations', 'secrets']

/** The dialog body's floor lives with the other record-surface metrics. */
const BODY_MIN_HEIGHT = RECORD_SURFACE.BODY_MIN_HEIGHT

/**
 * Stable identities: paging memoises on the row array, and `[]` written inline
 * would be a new array on every render while the provider is still loading.
 */
const EMPTY_OPERATIONS: IntegrationOperation[] = []
const EMPTY_SECRETS: IntegrationSecret[] = []

interface IntegrationDetailDialogProps {
  open: boolean
  onClose: () => void
  integrationId: string | null
}

export default function IntegrationDetailDialog({
  open,
  onClose,
  integrationId,
}: IntegrationDetailDialogProps) {
  const { t } = useTranslation('integration')
  const { t: tCommon } = useTranslation('common')
  const [tab, setTab] = useState<DetailTab>('operations')
  const [mode, setMode] = useState<PanelMode>({ kind: 'tabs' })
  const query = useIntegration(open ? integrationId : null)
  const provider = query.data

  const operationPaging = useTablePage(provider?.operations ?? EMPTY_OPERATIONS)
  const secretPaging = useTablePage(provider?.secrets ?? EMPTY_SECRETS)

  useQueryErrorToast(query, tCommon('messages.load_failed'))

  /**
   * The dialog stays mounted between openings, so its body has to be reset the
   * way a form dialog resets its fields: closed while inside the operation editor
   * or on the credentials tab, it would otherwise reopen exactly there — for a
   * different provider, since the row that opens it next is rarely the row that
   * closed it.
   *
   * The reset runs when the close transition has finished, not in an effect on
   * `open`: an effect that writes state is a second render pass React lints
   * against, and resetting on the click would show the body snapping back to the
   * tabs while the dialog is still fading out.
   */
  const resetBody = () => {
    setTab('operations')
    setMode({ kind: 'tabs' })
    operationPaging.reset()
    secretPaging.reset()
  }

  const panel = provider === undefined ? null : mode

  /** Resolved by key on every render, never held. */
  const selected =
    panel?.kind === 'operation'
      ? provider?.operations.find((operation) => operation.code === panel.operationCode)
      : undefined

  const selectedSecret =
    panel?.kind === 'secret'
      ? provider?.secrets.find((secret) => secret.name === panel.secretName)
      : undefined

  /**
   * The strip and the body are one surface. A mode whose key no longer resolves —
   * the record was deleted under it — falls back to the list, and the strip has to
   * come back with it or the tabs become unreachable.
   */
  const showsTabs =
    panel?.kind === 'tabs' ||
    (panel?.kind === 'operation' && selected === undefined) ||
    (panel?.kind === 'secret' && selectedSecret === undefined)

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      slotProps={{ transition: { onExited: resetBody } }}
    >
      <Stack direction="row" alignItems="flex-start" sx={{ p: 3, pb: 2 }}>
        <Stack spacing={1} sx={{ flexGrow: 1 }}>
          <Box>
            <Typography variant="h6">{provider?.display_name ?? t('detail_title')}</Typography>
            <Typography variant="caption" color="text.secondary">
              {provider?.code ?? ''}
            </Typography>
          </Box>

          {provider !== undefined && (
            <>
              <Stack direction="row" spacing={1}>
                <Label variant="soft" color="default">
                  {provider.base_url}
                </Label>
                <Label variant="soft" color={provider.enabled ? 'success' : 'default'}>
                  {provider.enabled ? tCommon('status.enabled') : tCommon('status.disabled')}
                </Label>
              </Stack>

              <Typography variant="caption" color="text.secondary">
                {t('detail_audit', {
                  user: provider.updated_by ?? tCommon('messages.unknown_actor'),
                  at: formatDateTime(provider.updated_at),
                  version: String(provider.version),
                })}
              </Typography>
            </>
          )}
        </Stack>

        <IconButton onClick={onClose} size="small">
          <Iconify name="close" />
        </IconButton>
      </Stack>

      {showsTabs && (
        <Tabs
          value={tab}
          onChange={(_event, value: DetailTab) => setTab(value)}
          sx={{ px: 3, borderBottom: 1, borderColor: 'divider' }}
        >
          {TAB_ORDER.map((name) => (
            <Tab
              key={name}
              value={name}
              label={t(`tabs.${name}`)}
              icon={<Iconify name={TAB_ICONS[name]} />}
            />
          ))}
        </Tabs>
      )}

      <DialogContent sx={{ minHeight: BODY_MIN_HEIGHT, bgcolor: 'background.neutral', p: 3 }}>
        {query.isLoading && (
          <Stack alignItems="center" sx={{ py: 6 }}>
            <CircularProgress />
          </Stack>
        )}

        {provider !== undefined && showsTabs && (
          <Box>
            {tab === 'operations' && (
              <IntegrationOperationsTab
                paging={operationPaging}
                onCreate={() => setMode({ kind: 'create' })}
                onSelect={(operation) =>
                  setMode({ kind: 'operation', operationCode: operation.code })
                }
                onDelete={(operation) => setMode({ kind: 'delete', operation })}
              />
            )}
            {tab === 'secrets' && (
              <IntegrationSecretsTab
                paging={secretPaging}
                onCreate={() => setMode({ kind: 'secretCreate' })}
                onSelect={(secret) => setMode({ kind: 'secret', secretName: secret.name })}
                onDelete={(secret) => setMode({ kind: 'secretDelete', secret })}
              />
            )}
          </Box>
        )}

        {provider !== undefined && (panel?.kind === 'create' || selected !== undefined) && (
          <IntegrationOperationPanel
            provider={provider}
            operation={selected ?? null}
            onRun={() => selected !== undefined && setMode({ kind: 'run', operation: selected })}
            // Reading or editing, "back" is the table the record was opened from.
            onBack={() => setMode({ kind: 'tabs' })}
          />
        )}

        {provider !== undefined &&
          (panel?.kind === 'secretCreate' || selectedSecret !== undefined) && (
            <IntegrationSecretPanel
              provider={provider}
              secret={selectedSecret ?? null}
              onBack={() => setMode({ kind: 'tabs' })}
            />
          )}

        {provider !== undefined && panel?.kind === 'run' && (
          <IntegrationRunPanel
            integrationId={provider.id}
            operation={panel.operation}
            onBack={() => setMode({ kind: 'operation', operationCode: panel.operation.code })}
          />
        )}

        {provider !== undefined && panel?.kind === 'delete' && (
          <IntegrationOperationDeletePanel
            provider={provider}
            operation={panel.operation}
            // Cancelling returns to the record; a completed delete cannot, so the
            // code resolves to nothing and the body falls back to the tab list.
            onBack={() => setMode({ kind: 'operation', operationCode: panel.operation.code })}
          />
        )}

        {provider !== undefined && panel?.kind === 'secretDelete' && (
          <IntegrationSecretDeletePanel
            provider={provider}
            secret={panel.secret}
            onBack={() => setMode({ kind: 'tabs' })}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
