import { useRef, useState } from 'react';
import { Check, FileText, ShieldCheck } from 'lucide-react';
import { extractPdfText, LocalPdfPasswordRequiredError } from '../utils/pdfTextExtractor';
import {
  formatTradeDateTime,
  formatTradeNumber,
  parseTradeCandidates,
  tradeSideLabel,
} from '../utils/brokerImport';

const MAX_PDF_BYTES = 25 * 1024 * 1024;

function isPdfFile(file) {
  return file?.type === 'application/pdf' || file?.name?.toLowerCase().endsWith('.pdf');
}

function resetImportState(setState) {
  setState({ status: 'idle', trades: [], selectedIds: new Set(), pageCount: 0, textItemCount: 0, message: '' });
}

export default function BrokerImport() {
  const fileInputRef = useRef(null);
  const [state, setState] = useState({
    status: 'idle',
    trades: [],
    selectedIds: new Set(),
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
        message: '프로토타입에서는 25MB 이하의 PDF만 처리합니다. 원본은 서버로 전송하지 않습니다.',
      }));
      return;
    }

    setState({ status: 'processing', trades: [], selectedIds: new Set(), pageCount: 0, textItemCount: 0, message: '' });
    try {
      let extraction = await extractPdfText(await file.arrayBuffer());
      const trades = parseTradeCandidates(extraction.text);
      const { pageCount, textItemCount } = extraction;
      extraction = null;
      setState({
        status: 'ready',
        trades,
        selectedIds: new Set(),
        pageCount,
        textItemCount,
        message: trades.length
          ? `${trades.length}건의 거래 후보를 찾았습니다. 각 항목은 합치지 않고 그대로 표시합니다.`
          : textItemCount
            ? 'PDF 텍스트는 읽었지만 현재 보수적인 후보 형식과 일치하는 거래가 없습니다.'
            : '텍스트가 없는 PDF입니다. 이미지·스캔 PDF의 OCR은 이번 프로토타입 범위에 포함하지 않습니다.',
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

  const clearImport = () => {
    resetImportState(setState);
  };

  const allSelected = state.trades.length > 0 && state.trades.every(trade => state.selectedIds.has(trade.id));
  const isProcessing = state.status === 'processing';

  return (
    <div className="broker-import-page">
      <header className="broker-import-header">
        <div>
          <span className="broker-import-eyebrow">LOCAL PDF PROTOTYPE</span>
          <h2>증권사 매매내역 PDF 가져오기</h2>
          <p>거래내역을 기기에서 읽고, 원하는 거래만 직접 선택합니다.</p>
        </div>
      </header>

      <section className="broker-import-privacy" aria-label="개인정보 보호 안내">
        <ShieldCheck size={22} aria-hidden="true" />
        <div>
          <strong>온디바이스 처리</strong>
          <span>PDF 원본과 전체 텍스트는 StockBoda backend·Render·외부 서버로 전송하거나 저장하지 않습니다.</span>
        </div>
      </section>

      <section className="broker-import-panel">
        <div className="broker-import-panel-heading">
          <div className="broker-import-file-icon" aria-hidden="true"><FileText size={24} /></div>
          <div>
            <h3>거래내역 PDF 선택</h3>
            <p>현재는 전자 텍스트 PDF만 지원합니다. 이미지·스캔 PDF와 실제 증권사별 서식 parser는 샘플 확인 후 확장합니다.</p>
          </div>
        </div>
        <input
          ref={fileInputRef}
          className="broker-import-file-input"
          type="file"
          accept="application/pdf,.pdf"
          onChange={handleFileChange}
          aria-label="증권사 거래내역 PDF 선택"
        />
        <div className="broker-import-actions">
          <button type="button" className="journal-primary" onClick={() => fileInputRef.current?.click()} disabled={isProcessing}>
            {isProcessing ? 'PDF 분석 중…' : 'PDF 파일 선택'}
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
              <strong>표시할 거래 후보가 없습니다.</strong>
              <span>실제 증권사 PDF 서식이 준비되면 해당 서식에 맞춘 parser를 추가할 수 있습니다.</span>
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
                  return (
                    <li key={trade.id} className={selected ? 'selected' : ''}>
                      <label className="broker-trade-card">
                        <input type="checkbox" checked={selected} onChange={() => toggleTrade(trade.id)} />
                        <span className={`broker-trade-side ${trade.side}`}>
                          {selected && <Check size={13} aria-hidden="true" />}
                          {tradeSideLabel(trade.side)}
                        </span>
                        <span className="broker-trade-main">
                          <strong>{trade.stockName}</strong>
                          <span className="broker-trade-meta">
                            {trade.symbol && <em>{trade.symbol}</em>}
                            <time>{formatTradeDateTime(trade)}</time>
                          </span>
                        </span>
                        <span className="broker-trade-amount">
                          <strong>{formatTradeNumber(trade.price)}원 × {formatTradeNumber(trade.quantity)}주</strong>
                          {(trade.fee !== null || trade.tax !== null) && (
                            <small>{trade.fee !== null ? `수수료 ${formatTradeNumber(trade.fee)}원` : ''}{trade.tax !== null ? ` 세금 ${formatTradeNumber(trade.tax)}원` : ''}</small>
                          )}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
              <p className="broker-import-next-step">선택한 거래를 기존 복기 화면이나 DB로 보내는 기능은 아직 연결하지 않았습니다.</p>
            </>
          )}
        </section>
      )}
    </div>
  );
}
