import { useRef, useState } from 'react';
import { Check, FileText, ShieldCheck } from 'lucide-react';
import { extractPdfText, LocalPdfPasswordRequiredError } from '../utils/pdfTextExtractor';
import {
  BROKER_STATEMENT_STATUS,
  REVIEW_TIME_VALIDATION_MESSAGES,
  createTradeTimeState,
  formatTradeDateTime,
  formatTradeNumber,
  parseBrokerStatement,
  setTradeTimeUnknownState,
  tradeSideLabel,
  validateTradeTimesForReview,
  updateTradeTimeState,
} from '../utils/brokerImport';

const MAX_PDF_BYTES = 25 * 1024 * 1024;

function isPdfFile(file) {
  return file?.type === 'application/pdf' || file?.name?.toLowerCase().endsWith('.pdf');
}

function resetImportState(setState) {
  setState({ status: 'idle', statementStatus: null, fileName: '', trades: [], selectedIds: new Set(), tradeStates: {}, pageCount: 0, textItemCount: 0, message: '' });
}

export default function BrokerImport({ onBackToJournal, onImportToJournal, embedded = false }) {
  const fileInputRef = useRef(null);
  const [state, setState] = useState({
    status: 'idle',
    statementStatus: null,
    fileName: '',
    trades: [],
    selectedIds: new Set(),
    tradeStates: {},
    pageCount: 0,
    textItemCount: 0,
    message: '',
  });

  const handleFileChange = async event => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    if (!isPdfFile(file)) {
      setState(previous => ({
        ...previous,
        status: 'error',
        statementStatus: null,
        fileName: file.name || '',
        trades: [],
        selectedIds: new Set(),
        tradeStates: {},
        pageCount: 0,
        textItemCount: 0,
        message: 'PDF 파일만 선택할 수 있습니다.',
      }));
      return;
    }
    if (file.size > MAX_PDF_BYTES) {
      setState(previous => ({
        ...previous,
        status: 'error',
        statementStatus: null,
        fileName: file.name || '',
        trades: [],
        selectedIds: new Set(),
        tradeStates: {},
        pageCount: 0,
        textItemCount: 0,
        message: '25MB 이하의 PDF만 처리할 수 있습니다. PDF 원본은 서버로 전송하지 않습니다.',
      }));
      return;
    }

    setState({ status: 'processing', statementStatus: null, fileName: file.name || '', trades: [], selectedIds: new Set(), tradeStates: {}, pageCount: 0, textItemCount: 0, message: '' });
    try {
      let extraction = await extractPdfText(await file.arrayBuffer());
      const parsed = parseBrokerStatement(extraction.text, extraction);
      const trades = parsed.trades;
      const { pageCount, textItemCount } = extraction;
      extraction = null;
      const tradeStates = Object.fromEntries(trades.map(trade => [trade.id, createTradeTimeState(trade.tradeTime)]));
      setState({
        status: 'ready',
        statementStatus: parsed.status,
        fileName: file.name || '',
        trades,
        selectedIds: new Set(),
        tradeStates,
        pageCount,
        textItemCount,
        message: '',
      });
    } catch (error) {
      const message = error instanceof LocalPdfPasswordRequiredError
        ? '비밀번호가 필요한 PDF는 현재 지원하지 않습니다. 비밀번호나 PDF 원본을 서버로 보내지 않습니다.'
        : error?.name === 'InvalidPDFException'
          ? '읽을 수 있는 PDF가 아닙니다. 텍스트 기반 PDF를 선택해 주세요.'
          : 'PDF를 기기에서 읽지 못했습니다. 파일을 다시 확인해 주세요.';
      setState(previous => ({ ...previous, status: 'error', message }));
    }
  };

  const toggleTrade = id => {
    setState(previous => {
      const selectedIds = new Set(previous.selectedIds);
      if (selectedIds.has(id)) selectedIds.delete(id);
      else selectedIds.add(id);
      return { ...previous, selectedIds };
    });
  };

  const toggleAll = () => {
    setState(previous => {
      const allSelected = previous.trades.length > 0 && previous.trades.every(trade => previous.selectedIds.has(trade.id));
      return {
        ...previous,
        selectedIds: allSelected ? new Set() : new Set(previous.trades.map(trade => trade.id)),
      };
    });
  };

  const updateTradeTime = (id, value) => {
    setState(previous => ({
      ...previous,
      tradeStates: {
        ...previous.tradeStates,
        [id]: updateTradeTimeState(previous.tradeStates[id] || createTradeTimeState(), value),
      },
    }));
  };

  const markTimeUnknown = (id, unknown) => {
    setState(previous => ({
      ...previous,
      tradeStates: {
        ...previous.tradeStates,
        [id]: setTradeTimeUnknownState(previous.tradeStates[id] || createTradeTimeState(), unknown),
      },
    }));
  };

  const clearImport = () => {
    resetImportState(setState);
  };

  const selectAnotherPdf = () => {
    fileInputRef.current?.click();
  };

  const allSelected = state.trades.length > 0 && state.trades.every(trade => state.selectedIds.has(trade.id));
  const isProcessing = state.status === 'processing';
  const selectedTrades = state.trades
    .filter(trade => state.selectedIds.has(trade.id))
    .map(trade => ({ ...trade, ...(state.tradeStates[trade.id] || createTradeTimeState()) }));
  const selectedTimeValidation = validateTradeTimesForReview(selectedTrades);
  const requiredTradeIds = new Set(selectedTimeValidation.requiredTradeIds);
  const missingRequiredTimeIds = new Set(selectedTimeValidation.missingTradeIds);
  const canImportSelectedTrades = selectedTrades.length > 0 && selectedTimeValidation.valid;

  const importSelectedTrades = () => {
    if (!selectedTrades.length) {
      setState(previous => ({ ...previous, message: '매매복기로 가져올 거래를 먼저 선택해 주세요.' }));
      return;
    }
    if (!selectedTimeValidation.valid) {
      setState(previous => ({
        ...previous,
        message: REVIEW_TIME_VALIDATION_MESSAGES.BLOCKED,
      }));
      return;
    }
    onImportToJournal?.(selectedTrades);
  };

  return (
    <div className={embedded ? 'broker-import-page broker-import-page-embedded' : 'broker-import-page'}>
      <header className={embedded ? 'broker-import-header broker-import-embedded-header' : 'broker-import-header'}>
        <div>
          <span className="broker-import-eyebrow">{embedded ? '거래내역 불러오기' : '매매복기 입력 방법'}</span>
          <h2>증권사 거래내역 불러오기</h2>
          <p>{embedded ? '거래내역 PDF에서 복기할 거래를 선택합니다.' : '거래내역서에서 복기할 거래를 골라 기존 매매복기를 준비합니다.'}</p>
        </div>
        {!embedded && onBackToJournal && (
          <button type="button" className="journal-secondary broker-import-back" onClick={onBackToJournal}>
            매매복기로 돌아가기
          </button>
        )}
      </header>

      <section className="broker-import-privacy" aria-label="개인정보 보호 안내">
        <ShieldCheck size={22} aria-hidden="true" />
        <div>
          <strong>🔒 거래내역서는 기기에서만 처리됩니다.</strong>
          <span>PDF 원본은 스톡보다 서버로 전송되거나 저장되지 않습니다.</span>
        </div>
      </section>

      {!embedded && <section className="broker-import-guide" aria-label="거래내역 불러오기 안내">
        <div className="broker-import-guide-step">
          <span className="broker-import-guide-number">1</span>
          <div>
            <strong>증권사 선택</strong>
            <p>토스증권 <em>1차 지원 예정</em></p>
          </div>
        </div>
        <div className="broker-import-guide-step">
          <span className="broker-import-guide-number">2</span>
          <div>
            <strong>거래내역서를 준비하세요</strong>
            <p>토스증권 앱에서 국내주식 거래내역서 PDF를 발급해 주세요.</p>
            <details className="broker-import-howto">
              <summary>발급 방법 보기</summary>
              <p>거래내역서 PDF를 준비한 뒤 아래 버튼에서 파일을 선택해 주세요. 정확한 메뉴 이름과 경로는 토스증권 앱의 최신 안내를 확인해 주세요.</p>
            </details>
          </div>
        </div>
        <div className="broker-import-guide-step">
          <span className="broker-import-guide-number">3</span>
          <div>
            <strong>PDF 선택</strong>
            <p>국내주식 거래내역서 PDF를 선택하면 복기할 거래를 고를 수 있습니다.</p>
          </div>
        </div>
      </section>}
      {embedded && <p className="broker-import-embedded-note">국내주식 · 첫 지원 예정: 토스증권</p>}

      <section className="broker-import-panel">
        <div className="broker-import-panel-heading">
          <div className="broker-import-file-icon" aria-hidden="true"><FileText size={24} /></div>
          <div>
            <h3>거래내역 PDF 선택</h3>
            <p>전자 텍스트 PDF만 지원합니다. 사진이나 스캔 문서는 현재 지원하지 않습니다.</p>
          </div>
        </div>
        {state.fileName && (
          <div className="broker-import-selected-file" aria-live="polite">
            <span>선택한 파일</span>
            <strong title={state.fileName}>{state.fileName}</strong>
            {state.pageCount > 0 && <small>{state.pageCount}페이지</small>}
          </div>
        )}
        <input
          ref={fileInputRef}
          className="broker-import-file-input"
          type="file"
          accept="application/pdf,.pdf"
          onChange={handleFileChange}
          aria-label="거래내역 PDF 선택"
        />
        <div className="broker-import-actions">
          <button type="button" className="journal-primary" onClick={selectAnotherPdf} disabled={isProcessing}>
            {isProcessing ? '거래내역 확인 중…' : state.status === 'idle' ? '거래내역 PDF 선택' : '다른 PDF 선택'}
          </button>
          <button type="button" className="journal-secondary" onClick={clearImport} disabled={isProcessing || state.status === 'idle'}>
            선택 내용 지우기
          </button>
        </div>
        {isProcessing && <p className="broker-import-status" role="status">PDF를 기기 안에서 분석하고 있습니다. 잠시만 기다려 주세요.</p>}
        {state.message && state.status !== 'processing' && (
          <p className={`broker-import-message ${state.status === 'error' ? 'error' : ''}`} role={state.status === 'error' ? 'alert' : 'status'}>
            {state.message}
          </p>
        )}
      </section>

      {state.status === 'ready' && state.statementStatus === BROKER_STATEMENT_STATUS.READY && (
        <section className="broker-import-results">
          <div className="broker-import-results-heading">
            <div>
              <h3>복기할 거래 선택</h3>
              <p>{state.trades.length}건의 거래를 확인했습니다.</p>
            </div>
            {state.trades.length > 0 && (
              <span className="broker-import-selected-count">{state.selectedIds.size}건 선택</span>
            )}
          </div>

          {state.trades.length === 0 ? (
            <div className="broker-import-empty">
              <strong>가져올 거래가 없습니다.</strong>
              <span>현재 지원되는 국내주식 거래내역서 형식과 일치하는 거래가 없습니다.</span>
            </div>
          ) : (
            <>
              <div className="broker-import-selection-toolbar">
                <label>
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                  전체 선택
                </label>
                <span>선택 상태는 현재 화면과 메모리에서만 유지됩니다.</span>
              </div>
              {selectedTimeValidation.requiredGroups.length > 0 && (
                <div
                  className={`broker-import-time-warning ${selectedTimeValidation.valid ? 'complete' : ''}`}
                  role={selectedTimeValidation.valid ? 'status' : 'alert'}
                >
                  <strong>{selectedTimeValidation.valid ? '체결시간을 확인했습니다' : '⚠ 체결시간이 필요합니다'}</strong>
                  <span>같은 날 매수와 매도가 함께 선택되었습니다.</span>
                  <p>정확한 거래 순서를 확인하려면 체결시간이 필요합니다.</p>
                  {selectedTimeValidation.valid && <small>필수 거래의 체결시간이 모두 입력되었습니다.</small>}
                </div>
              )}
              <ul className="broker-trade-list">
                {state.trades.map(trade => {
                  const selected = state.selectedIds.has(trade.id);
                  const tradeState = state.tradeStates[trade.id] || createTradeTimeState();
                  const { tradeTime, timeUnknown } = tradeState;
                  const timeRequired = selected && requiredTradeIds.has(trade.id);
                  const missingRequiredTime = timeRequired && missingRequiredTimeIds.has(trade.id);
                  return (
                    <li key={trade.id} className={`${selected ? 'selected' : ''}${missingRequiredTime ? ' time-required' : ''}`}>
                      <div className="broker-trade-card" onClick={() => toggleTrade(trade.id)}>
                        <input type="checkbox" checked={selected} onClick={event => event.stopPropagation()} onChange={() => toggleTrade(trade.id)} />
                        <span className={`broker-trade-side ${trade.side}`}>
                          {selected && <Check size={13} aria-hidden="true" />}
                          {tradeSideLabel(trade.side)}
                        </span>
                        <span className="broker-trade-main">
                          <strong>{trade.stockName}</strong>
                          <span className="broker-trade-meta">
                            {trade.symbol && <em>{trade.symbol}</em>}
                            <time>{formatTradeDateTime({ ...trade, tradeTime })}</time>
                          </span>
                        </span>
                        <span className="broker-trade-amount">
                          <strong>{formatTradeNumber(trade.price)}원 × {formatTradeNumber(trade.quantity)}주</strong>
                          {(trade.fee !== null || trade.tax !== null) && (
                            <small>{trade.fee !== null ? `수수료 ${formatTradeNumber(trade.fee)}원` : ''}{trade.tax !== null ? ` 세금 ${formatTradeNumber(trade.tax)}원` : ''}</small>
                          )}
                        </span>
                        {selected && (
                          <div className="broker-trade-time" onClick={event => event.stopPropagation()}>
                            <span>{timeRequired ? '체결시간(필수)' : '체결시간(선택)'}</span>
                            <input
                              type="time"
                              value={tradeTime ?? ''}
                              disabled={timeUnknown}
                              required={timeRequired && !timeUnknown}
                              aria-invalid={missingRequiredTime}
                              onChange={event => updateTradeTime(trade.id, event.target.value)}
                              aria-label={`${trade.stockName} 체결시간`}
                            />
                            <label>
                              <input
                                type="checkbox"
                                checked={timeUnknown}
                                onChange={event => markTimeUnknown(trade.id, event.target.checked)}
                              />
                              시간을 모름
                            </label>
                          </div>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
              <div className="broker-import-actions broker-import-transfer-actions">
                <button
                  type="button"
                  className="journal-primary"
                  onClick={importSelectedTrades}
                  disabled={!canImportSelectedTrades}
                  aria-describedby="broker-import-transfer-hint"
                >
                  매매 복기로 가져오기
                </button>
              </div>
              <p className={`broker-import-next-step broker-import-transfer-hint${canImportSelectedTrades ? ' ready' : ''}`} id="broker-import-transfer-hint" role="status">
                {!selectedTrades.length
                  ? '거래를 선택하면 매매 복기로 가져올 수 있습니다.'
                  : !selectedTimeValidation.valid
                    ? '필수 체결시간을 입력하면 매매 복기로 가져올 수 있습니다.'
                    : '선택한 거래를 매매 복기로 준비합니다.'}{' '}
                PDF에서 읽은 정보만 준비합니다.{' '}
                {selectedTimeValidation.requiredGroups.length > 0
                  ? '같은 날 같은 종목의 매수와 매도가 함께 선택되어 있습니다. 정확한 거래 순서를 위해 해당 거래의 체결시간을 입력해주세요.'
                  : '거래내역서에 체결시간이 없는 경우 비워둘 수 있습니다.'}{' '}
                매매 이유와 판단은 매매복기에서 작성합니다.
              </p>
            </>
          )}
        </section>
      )}

      {state.status === 'ready' && state.statementStatus === BROKER_STATEMENT_STATUS.OVERSEAS_UNSUPPORTED && (
        <section className="broker-import-state-card broker-import-state-unsupported" role="status">
          <span className="broker-import-state-label">지원 범위 안내</span>
          <h3>해외주식 거래내역은 아직 지원하지 않습니다.</h3>
          <p>선택한 PDF는 해외주식 거래내역서입니다.</p>
          <p>현재는 토스증권 국내주식 거래내역만 지원합니다.</p>
          <button type="button" className="journal-primary" onClick={selectAnotherPdf}>다른 PDF 선택</button>
        </section>
      )}

      {state.status === 'ready'
        && (state.statementStatus === BROKER_STATEMENT_STATUS.NO_CANDIDATES
          || state.statementStatus === BROKER_STATEMENT_STATUS.TOSS_DOMESTIC_SAMPLE_REQUIRED) && (
        <section className="broker-import-state-card broker-import-state-unrecognized" role="status">
          <span className="broker-import-state-label">거래내역 확인</span>
          <h3>거래내역을 인식하지 못했습니다.</h3>
          <p>현재 지원되는 토스증권 국내주식 거래내역서인지 확인해주세요.</p>
          <button type="button" className="journal-primary" onClick={selectAnotherPdf}>다른 PDF 선택</button>
        </section>
      )}
    </div>
  );
}
