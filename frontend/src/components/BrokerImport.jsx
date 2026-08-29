import { useRef, useState } from 'react';
import { Check, FileText, ShieldCheck } from 'lucide-react';
import { extractPdfText, LocalPdfPasswordRequiredError } from '../utils/pdfTextExtractor';
import {
  BROKER_STATEMENT_MESSAGES,
  BROKER_STATEMENT_STATUS,
  createTradeTimeState,
  formatTradeDateTime,
  formatTradeNumber,
  parseBrokerStatement,
  setTradeTimeUnknownState,
  tradeSideLabel,
  updateTradeTimeState,
} from '../utils/brokerImport';

const MAX_PDF_BYTES = 25 * 1024 * 1024;

function isPdfFile(file) {
  return file?.type === 'application/pdf' || file?.name?.toLowerCase().endsWith('.pdf');
}

function resetImportState(setState) {
  setState({ status: 'idle', trades: [], selectedIds: new Set(), tradeStates: {}, pageCount: 0, textItemCount: 0, message: '' });
}

export default function BrokerImport({ onBackToJournal, onImportToJournal }) {
  const fileInputRef = useRef(null);
  const [state, setState] = useState({
    status: 'idle',
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
      setState(previous => ({ ...previous, status: 'error', message: 'PDF 파일만 선택할 수 있습니다.' }));
      return;
    }
    if (file.size > MAX_PDF_BYTES) {
      setState(previous => ({
        ...previous,
        status: 'error',
        message: '25MB 이하의 PDF만 처리할 수 있습니다. PDF 원본은 서버로 전송하지 않습니다.',
      }));
      return;
    }

    setState({ status: 'processing', trades: [], selectedIds: new Set(), tradeStates: {}, pageCount: 0, textItemCount: 0, message: '' });
    try {
      let extraction = await extractPdfText(await file.arrayBuffer());
      const parsed = parseBrokerStatement(extraction.text);
      const trades = parsed.trades;
      const { pageCount, textItemCount } = extraction;
      extraction = null;
      const tradeStates = Object.fromEntries(trades.map(trade => [trade.id, createTradeTimeState(trade.tradeTime)]));
      const message = parsed.status === BROKER_STATEMENT_STATUS.OVERSEAS_UNSUPPORTED
        ? BROKER_STATEMENT_MESSAGES.OVERSEAS_UNSUPPORTED
        : parsed.status === BROKER_STATEMENT_STATUS.TOSS_DOMESTIC_SAMPLE_REQUIRED
          ? BROKER_STATEMENT_MESSAGES.TOSS_DOMESTIC_SAMPLE_REQUIRED
          : trades.length
            ? `${trades.length}건의 거래를 찾았습니다. 각 거래는 합치지 않고 그대로 표시합니다.`
            : textItemCount
              ? '거래내역은 읽었지만 현재 지원되는 국내주식 형식의 거래를 찾지 못했습니다.'
              : '텍스트가 없는 PDF입니다. 사진이나 스캔 문서는 현재 지원하지 않습니다.';
      setState({
        status: 'ready',
        trades,
        selectedIds: new Set(),
        tradeStates,
        pageCount,
        textItemCount,
        message,
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

  const allSelected = state.trades.length > 0 && state.trades.every(trade => state.selectedIds.has(trade.id));
  const isProcessing = state.status === 'processing';
  const selectedTrades = state.trades
    .filter(trade => state.selectedIds.has(trade.id))
    .map(trade => ({ ...trade, ...(state.tradeStates[trade.id] || createTradeTimeState()) }));

  const importSelectedTrades = () => {
    if (!selectedTrades.length) {
      setState(previous => ({ ...previous, message: '매매복기로 가져올 거래를 먼저 선택해 주세요.' }));
      return;
    }
    onImportToJournal?.(selectedTrades);
  };

  return (
    <div className="broker-import-page">
      <header className="broker-import-header">
        <div>
          <span className="broker-import-eyebrow">매매복기 입력 방법</span>
          <h2>증권사 거래내역 불러오기</h2>
          <p>거래내역서에서 복기할 거래를 골라 기존 매매복기를 준비합니다.</p>
        </div>
        {onBackToJournal && (
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

      <section className="broker-import-guide" aria-label="거래내역 불러오기 안내">
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
      </section>

      <section className="broker-import-panel">
        <div className="broker-import-panel-heading">
          <div className="broker-import-file-icon" aria-hidden="true"><FileText size={24} /></div>
          <div>
            <h3>국내주식 거래내역 PDF 선택</h3>
            <p>전자 텍스트 PDF만 지원합니다. 사진이나 스캔 문서는 현재 지원하지 않습니다.</p>
          </div>
        </div>
        <input
          ref={fileInputRef}
          className="broker-import-file-input"
          type="file"
          accept="application/pdf,.pdf"
          onChange={handleFileChange}
          aria-label="거래내역 PDF 선택"
        />
        <div className="broker-import-actions">
          <button type="button" className="journal-primary" onClick={() => fileInputRef.current?.click()} disabled={isProcessing}>
            {isProcessing ? '거래내역 확인 중…' : '거래내역 PDF 선택'}
          </button>
          <button type="button" className="journal-secondary" onClick={clearImport} disabled={isProcessing && state.trades.length === 0}>
            초기화
          </button>
        </div>
        {isProcessing && <p className="broker-import-status" role="status">PDF를 기기 안에서 분석하고 있습니다. 잠시만 기다려 주세요.</p>}
        {state.message && state.status !== 'processing' && (
          <p className={`broker-import-message ${state.status === 'error' ? 'error' : ''}`} role={state.status === 'error' ? 'alert' : 'status'}>
            {state.message}
          </p>
        )}
      </section>

      {state.status === 'ready' && (
        <section className="broker-import-results">
          <div className="broker-import-results-heading">
            <div>
              <h3>거래 후보</h3>
              <p>{state.pageCount}페이지 · {state.trades.length}건 · 최신 날짜/시간순</p>
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
              <ul className="broker-trade-list">
                {state.trades.map(trade => {
                  const selected = state.selectedIds.has(trade.id);
                  const tradeState = state.tradeStates[trade.id] || createTradeTimeState();
                  const { tradeTime, timeUnknown } = tradeState;
                  return (
                    <li key={trade.id} className={selected ? 'selected' : ''}>
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
                            <span>체결시간</span>
                            <input
                              type="time"
                              value={tradeTime ?? ''}
                              disabled={timeUnknown}
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
                <button type="button" className="journal-primary" onClick={importSelectedTrades}>
                  선택한 거래를 매매복기로 가져오기
                </button>
              </div>
              <p className="broker-import-next-step">PDF에서 읽은 정보만 준비합니다. 체결시간을 모르면 비워 둘 수 있고, 매매 이유와 판단은 매매복기에서 작성합니다.</p>
            </>
          )}
        </section>
      )}
    </div>
  );
}
