import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, HeatmapChart, LineChart, ScatterChart } from 'echarts/charts';
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkAreaComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { EChartsCoreOption } from 'echarts/core';

echarts.use([
  LineChart,
  BarChart,
  HeatmapChart,
  ScatterChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
  MarkAreaComponent,
  VisualMapComponent,
  DataZoomComponent,
  CanvasRenderer,
]);

export interface ChartClick {
  seriesId?: string;
  dataIndex: number;
  value: unknown;
}

interface Props {
  option: EChartsCoreOption;
  height: number;
  ariaLabel: string;
  onClick?: (e: ChartClick) => void;
}

/** Thin, tree-shaken ECharts wrapper (no extra React binding dependency). */
export function EChart({ option, height, ariaLabel, onClick }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const clickRef = useRef(onClick);

  useEffect(() => {
    clickRef.current = onClick;
  }, [onClick]);

  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current, undefined, { renderer: 'canvas' });
    chart.current = c;
    c.on('click', (p) => {
      const params = p as unknown as ChartClick;
      clickRef.current?.({ seriesId: params.seriesId, dataIndex: params.dataIndex, value: params.value });
    });
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption(option, { notMerge: true });
  }, [option]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: '100%' }} />;
}
