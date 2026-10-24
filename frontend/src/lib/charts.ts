/** Pure transforms from API responses to chart-ready structures and ECharts options. */

import type { EChartsCoreOption } from 'echarts/core';
import type { Analysis, DeliveryDay, Interval, Revisions, Vintage } from '../api/types';
import { fmtDateTime, fmtMW, fmtShortDay, fmtTime } from './format';

export const COLORS = {
  actual: '#38cdb0',
  forecast: '#f2b33d',
  later: '#9d8cf0',
  earlier: '#5d6878',
  selected: '#7cc4ff',
  over: '#ec7a62',
  under: '#4f9ee8',
  grid: '#232b36',
  axis: '#8a94a3',
  text: '#d9dee6',
  missing: '#2a313c',
};

const AXIS_COMMON = {
  axisLine: { lineStyle: { color: COLORS.grid } },
  axisTick: { show: false },
  axisLabel: { color: COLORS.axis, fontSize: 11 },
  splitLine: { lineStyle: { color: COLORS.grid } },
};

const TOOLTIP_COMMON = {
  backgroundColor: '#11161d',
  borderColor: '#2c3542',
  textStyle: { color: COLORS.text, fontSize: 12 },
  extraCssText: 'box-shadow: 0 6px 24px rgba(0,0,0,.4); border-radius: 6px;',
};

export interface Slot {
  t: string;
  label: string;
  actual: number | null;
  forecast: number | null;
  error: number | null;
  interval: Interval | null;
}

/**
 * Half-hourly slots for a delivery day. Actuals are half-hourly; eligible
 * forecasts exist only on the hour (WINDFOR resolution), so forecast/error are
 * null on :30 slots. Labels are Europe/London wall-clock times.
 */
export function buildSlots(day: Pick<DeliveryDay, 'intervals' | 'actual_series'>): Slot[] {
  const byT = new Map<string, Slot>();
  const key = (iso: string) => new Date(iso).toISOString();
  for (const i of day.intervals) {
    const k = key(i.start_time);
    byT.set(k, { t: k, label: fmtTime(k), actual: i.actual_mw, forecast: i.forecast_mw, error: i.error_mw, interval: i });
    const half = new Date(new Date(k).getTime() + 30 * 60_000).toISOString();
    byT.set(half, { t: half, label: fmtTime(half), actual: null, forecast: null, error: null, interval: null });
  }
  for (const a of day.actual_series) {
    const k = key(a.start_time);
    const s = byT.get(k);
    if (s) s.actual = a.generation_mw;
  }
  return [...byT.values()].sort((a, b) => a.t.localeCompare(b.t));
}

export function cockpitOption(day: DeliveryDay, selectedT: string | null): EChartsCoreOption {
  const slots = buildSlots(day);
  const labels = slots.map((s) => s.label);
  const selIdx = selectedT ? slots.findIndex((s) => s.t === new Date(selectedT).toISOString()) : -1;
  const missingAreas = slots
    .filter((s) => s.interval && s.interval.status !== 'matched')
    .map((s) => [{ xAxis: s.label }, { xAxis: fmtTime(new Date(new Date(s.t).getTime() + 60 * 60_000).toISOString()) }]);
  return {
    animation: false,
    grid: [
      { left: 64, right: 24, top: 36, height: '56%' },
      { left: 64, right: 24, top: '74%', bottom: 28 },
    ],
    legend: {
      top: 0,
      left: 60,
      textStyle: { color: COLORS.axis, fontSize: 12 },
      itemWidth: 16,
      data: ['Actual (FUELHH, half-hourly)', 'Eligible forecast (WINDFOR, hourly)', 'Error (F − A)'],
    },
    tooltip: {
      ...TOOLTIP_COMMON,
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: '#4a5566' } },
      formatter: (params: Array<{ dataIndex: number }>) => {
        const s = slots[params[0]?.dataIndex ?? 0];
        if (!s) return '';
        const rows = [`<b>${fmtDateTime(s.t)}</b>`, `Actual: <b>${fmtMW(s.actual)} MW</b>`];
        if (s.interval) {
          rows.push(`Forecast: <b>${fmtMW(s.forecast)} MW</b>`);
          rows.push(`Error: <b>${fmtMW(s.error, { signed: true })} MW</b>`);
          rows.push(`<span style="color:#8a94a3">Published ${fmtDateTime(s.interval.publish_time)}</span>`);
        } else {
          rows.push('<span style="color:#8a94a3">:30 slot — WINDFOR is hourly</span>');
        }
        return rows.join('<br/>');
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    xAxis: [
      { type: 'category', data: labels, gridIndex: 0, boundaryGap: false, ...AXIS_COMMON, axisLabel: { show: false } },
      {
        type: 'category',
        data: labels,
        gridIndex: 1,
        boundaryGap: false,
        ...AXIS_COMMON,
        axisLabel: { color: COLORS.axis, fontSize: 11, interval: 5 },
      },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, name: 'MW', nameTextStyle: { color: COLORS.axis }, ...AXIS_COMMON, scale: true },
      { type: 'value', gridIndex: 1, name: 'Error MW', nameTextStyle: { color: COLORS.axis }, ...AXIS_COMMON },
    ],
    series: [
      {
        id: 'actual',
        name: 'Actual (FUELHH, half-hourly)',
        type: 'line',
        data: slots.map((s) => s.actual),
        showSymbol: false,
        lineStyle: { width: 2, color: COLORS.actual },
        itemStyle: { color: COLORS.actual },
        connectNulls: false,
        markArea: missingAreas.length
          ? { silent: true, itemStyle: { color: 'rgba(236,122,98,0.08)' }, data: missingAreas }
          : undefined,
        markLine:
          selIdx >= 0
            ? {
                symbol: 'none',
                silent: true,
                lineStyle: { color: COLORS.selected, type: 'solid', width: 1 },
                label: { show: false },
                data: [{ xAxis: selIdx }],
              }
            : undefined,
      },
      {
        id: 'forecast',
        name: 'Eligible forecast (WINDFOR, hourly)',
        type: 'line',
        data: slots.map((s) => s.forecast),
        connectNulls: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { width: 2, color: COLORS.forecast },
        itemStyle: { color: COLORS.forecast },
      },
      {
        id: 'error',
        name: 'Error (F − A)',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        barWidth: '70%',
        data: slots.map((s) =>
          s.error === null ? null : { value: s.error, itemStyle: { color: s.error >= 0 ? COLORS.over : COLORS.under } },
        ),
        itemStyle: { color: COLORS.over },
      },
    ],
  };
}

export function slotAt(day: DeliveryDay, dataIndex: number): Slot | undefined {
  const slots = buildSlots(day);
  const s = slots[dataIndex];
  if (!s) return undefined;
  if (s.interval) return s;
  // :30 slot → snap to the preceding hourly interval.
  return slots[dataIndex - 1]?.interval ? slots[dataIndex - 1] : undefined;
}

export function vintageRole(v: Vintage): 'decision' | 'earlier' | 'later' {
  if (v.is_decision_vintage) return 'decision';
  return v.eligible ? 'earlier' : 'later';
}

export function revisionsOption(rev: Revisions, selectedPub: string | null, selectedT: string | null): EChartsCoreOption {
  const targets = rev.decision_intervals.map((i) => new Date(i.start_time).toISOString());
  const labels = targets.map(fmtTime);
  const actualByT = new Map(rev.actual_series.map((a) => [new Date(a.start_time).toISOString(), a.generation_mw]));
  const selIso = selectedPub ? new Date(selectedPub).toISOString() : null;
  const selTIdx = selectedT ? targets.indexOf(new Date(selectedT).toISOString()) : -1;

  const series: object[] = rev.vintages.map((v) => {
    const role = vintageRole(v);
    const isSel = selIso === new Date(v.publish_time).toISOString();
    const byT = new Map(v.points.map((p) => [new Date(p.start_time).toISOString(), p.generation_mw]));
    const color = isSel ? COLORS.selected : role === 'decision' ? COLORS.forecast : role === 'later' ? COLORS.later : COLORS.earlier;
    return {
      id: `v-${v.publish_time}`,
      name: role === 'decision' ? 'Decision vintage' : role === 'later' ? 'Published after cutoff' : 'Earlier eligible',
      type: 'line',
      data: targets.map((t) => byT.get(t) ?? null),
      showSymbol: isSel || role === 'decision',
      symbolSize: 4,
      z: isSel ? 10 : role === 'decision' ? 9 : 2,
      lineStyle: {
        color,
        width: isSel || role === 'decision' ? 2.5 : 1,
        type: role === 'later' && !isSel ? 'dashed' : 'solid',
        opacity: isSel || role === 'decision' ? 1 : 0.45,
      },
      itemStyle: { color },
      emphasis: { disabled: true },
    };
  });
  series.push({
    id: 'actual',
    name: 'Actual',
    type: 'line',
    data: targets.map((t) => actualByT.get(t) ?? null),
    showSymbol: false,
    z: 11,
    lineStyle: { color: COLORS.actual, width: 2.5 },
    itemStyle: { color: COLORS.actual },
    markLine:
      selTIdx >= 0
        ? { symbol: 'none', silent: true, label: { show: false }, lineStyle: { color: COLORS.selected }, data: [{ xAxis: selTIdx }] }
        : undefined,
  });

  return {
    animation: false,
    grid: { left: 64, right: 24, top: 36, bottom: 32 },
    legend: {
      top: 0,
      left: 60,
      textStyle: { color: COLORS.axis, fontSize: 12 },
      data: ['Actual', 'Decision vintage', 'Earlier eligible', 'Published after cutoff'],
    },
    tooltip: {
      ...TOOLTIP_COMMON,
      trigger: 'axis',
      formatter: (params: Array<{ dataIndex: number }>) => {
        const idx = params[0]?.dataIndex ?? 0;
        const t = targets[idx];
        if (!t) return '';
        const dec = rev.decision_intervals[idx];
        const sel = selIso ? rev.vintages.find((v) => new Date(v.publish_time).toISOString() === selIso) : undefined;
        const selVal = sel?.points.find((p) => new Date(p.start_time).toISOString() === t)?.generation_mw;
        const rows = [
          `<b>${fmtDateTime(t)}</b>`,
          `Actual: <b>${fmtMW(actualByT.get(t))} MW</b>`,
          `Decision forecast: <b>${fmtMW(dec?.forecast_mw)} MW</b>`,
        ];
        if (sel) rows.push(`Selected vintage: <b>${fmtMW(selVal)} MW</b>`);
        return rows.join('<br/>');
      },
    },
    xAxis: { type: 'category', data: labels, boundaryGap: false, ...AXIS_COMMON, axisLabel: { color: COLORS.axis, interval: 2 } },
    yAxis: { type: 'value', name: 'MW', nameTextStyle: { color: COLORS.axis }, scale: true, ...AXIS_COMMON },
    series,
  };
}

export function dailyOption(a: Analysis, selectedDecision: string | null): EChartsCoreOption {
  const labels = a.daily.map((d) => fmtShortDay(d.delivery_date));
  return {
    animation: false,
    grid: { left: 64, right: 56, top: 36, bottom: 32 },
    legend: { top: 0, left: 60, textStyle: { color: COLORS.axis, fontSize: 12 }, data: ['Daily MAE', 'Daily mean bias'] },
    tooltip: {
      ...TOOLTIP_COMMON,
      trigger: 'axis',
      formatter: (params: Array<{ dataIndex: number }>) => {
        const d = a.daily[params[0]?.dataIndex ?? 0];
        if (!d) return '';
        return [
          `<b>Delivery ${fmtShortDay(d.delivery_date)}</b> <span style="color:#8a94a3">(decision ${fmtShortDay(d.decision_date)})</span>`,
          `MAE: <b>${fmtMW(d.mae_mw)} MW</b>`,
          `Bias: <b>${fmtMW(d.bias_mw, { signed: true })} MW</b>`,
          `Matched: ${d.coverage.matched}/${d.coverage.expected}`,
          '<span style="color:#8a94a3">Click to open in cockpit</span>',
        ].join('<br/>');
      },
    },
    xAxis: { type: 'category', data: labels, ...AXIS_COMMON, axisLabel: { color: COLORS.axis, interval: 2 } },
    yAxis: [
      { type: 'value', name: 'MAE MW', nameTextStyle: { color: COLORS.axis }, ...AXIS_COMMON },
      { type: 'value', name: 'Bias MW', nameTextStyle: { color: COLORS.axis }, ...AXIS_COMMON, splitLine: { show: false } },
    ],
    series: [
      {
        id: 'mae',
        name: 'Daily MAE',
        type: 'bar',
        data: a.daily.map((d) => ({
          value: d.mae_mw,
          itemStyle: { color: d.decision_date === selectedDecision ? COLORS.selected : '#3d6f8f' },
        })),
        itemStyle: { color: '#3d6f8f' },
        barWidth: '60%',
      },
      {
        id: 'bias',
        name: 'Daily mean bias',
        type: 'line',
        yAxisIndex: 1,
        data: a.daily.map((d) => d.bias_mw),
        connectNulls: false,
        lineStyle: { color: COLORS.forecast, width: 2 },
        itemStyle: { color: COLORS.forecast },
        symbolSize: 4,
        markLine: { symbol: 'none', silent: true, lineStyle: { color: '#4a5566', type: 'dashed' }, label: { show: false }, data: [{ yAxis: 0 }] },
      },
    ],
  };
}

export function histogramOption(a: Analysis): EChartsCoreOption {
  const labels = a.histogram.map((b) => `${fmtMW(b.lower_mw)}`);
  const p = a.error_percentiles;
  const idxOf = (v: number | null) => (v === null ? -1 : a.histogram.findIndex((b) => v >= b.lower_mw && v < b.upper_mw));
  const marks = [
    { name: 'P5', v: p.p05_mw },
    { name: 'Median', v: p.p50_mw },
    { name: 'P95', v: p.p95_mw },
  ]
    .filter((m) => idxOf(m.v) >= 0)
    .map((m) => ({ xAxis: idxOf(m.v), label: { formatter: `${m.name} ${fmtMW(m.v, { signed: true })}`, color: COLORS.text, fontSize: 11 } }));
  return {
    animation: false,
    grid: { left: 56, right: 24, top: 32, bottom: 44 },
    tooltip: {
      ...TOOLTIP_COMMON,
      trigger: 'axis',
      formatter: (params: Array<{ dataIndex: number }>) => {
        const b = a.histogram[params[0]?.dataIndex ?? 0];
        if (!b) return '';
        return `Error ${fmtMW(b.lower_mw, { signed: true })} to ${fmtMW(b.upper_mw, { signed: true })} MW<br/><b>${b.count}</b> intervals`;
      },
    },
    xAxis: {
      type: 'category',
      data: labels,
      name: 'Error MW (forecast − actual)',
      nameLocation: 'middle',
      nameGap: 28,
      nameTextStyle: { color: COLORS.axis },
      ...AXIS_COMMON,
    },
    yAxis: { type: 'value', name: 'Intervals', nameTextStyle: { color: COLORS.axis }, ...AXIS_COMMON },
    series: [
      {
        type: 'bar',
        barCategoryGap: '8%',
        data: a.histogram.map((b) => ({
          value: b.count,
          itemStyle: { color: b.upper_mw <= 0 ? COLORS.under : b.lower_mw >= 0 ? COLORS.over : '#8a94a3' },
        })),
        markLine: { symbol: 'none', silent: true, lineStyle: { color: '#cfd6df', type: 'dashed' }, data: marks },
      },
    ],
  };
}

export function heatmapOption(a: Analysis): EChartsCoreOption {
  const days = a.daily.map((d) => d.delivery_date);
  const dayIdx = new Map(days.map((d, i) => [d, i]));
  const hours = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, '0')}:00`);
  const data = a.heatmap.map((c) => [c.hour_local, dayIdx.get(c.delivery_date) ?? 0, c.error_mw ?? '-']);
  const maxAbs = Math.max(1000, ...a.heatmap.map((c) => Math.abs(c.error_mw ?? 0)));
  const bound = Math.ceil(maxAbs / 1000) * 1000;
  return {
    animation: false,
    grid: { left: 64, right: 24, top: 12, bottom: 72 },
    tooltip: {
      ...TOOLTIP_COMMON,
      formatter: (p: { value: [number, number, number | string] }) => {
        const [h, d, v] = p.value;
        return `<b>Delivery ${fmtShortDay(days[d] ?? '')} ${hours[h]}</b><br/>Error: <b>${
          typeof v === 'number' ? `${fmtMW(v, { signed: true })} MW` : 'no matched pair'
        }</b>`;
      },
    },
    xAxis: { type: 'category', data: hours, ...AXIS_COMMON, splitArea: { show: false }, axisLabel: { color: COLORS.axis, interval: 2 } },
    yAxis: {
      type: 'category',
      data: days.map(fmtShortDay),
      inverse: true,
      ...AXIS_COMMON,
      axisLabel: { color: COLORS.axis, fontSize: 10, interval: 1 },
    },
    visualMap: {
      type: 'continuous',
      min: -bound,
      max: bound,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 4,
      itemHeight: 220,
      itemWidth: 10,
      text: ['Over-forecast', 'Under-forecast'],
      textStyle: { color: COLORS.axis, fontSize: 11 },
      inRange: { color: ['#2166ac', '#4f9ee8', '#1b222c', '#ec7a62', '#b2182b'] },
      outOfRange: { color: COLORS.missing },
    },
    series: [{ type: 'heatmap', data, itemStyle: { borderColor: '#0f1419', borderWidth: 1 }, emphasis: { itemStyle: { borderColor: '#fff' } } }],
  };
}
