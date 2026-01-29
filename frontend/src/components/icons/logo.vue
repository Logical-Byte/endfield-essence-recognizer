<template>
  <svg viewBox="-6 -6 12 12" xmlns="http://www.w3.org/2000/svg">
    <!-- 实心圆盘，半径6 -->
    <circle cx="0" cy="0" r="6" style="fill: var(--bg, transparent)" />
    <!-- 空心圆，外径5，内径4 -->
    <circle cx="0" cy="0" r="4.5" fill="none" stroke="currentColor" stroke-width="1" />
    <!-- 空心圆，外径2，内径1 -->
    <circle cx="0" cy="0" r="1.5" fill="none" stroke="currentColor" stroke-width="1" />
    <!-- 连接两个圆的线 -->
    <line x1="-4.5" y1="0" x2="-1.5" y2="0" stroke="currentColor" stroke-width="1" />
    <line x1="4.5" y1="0" x2="1.5" y2="0" stroke="currentColor" stroke-width="1" />
  </svg>
</template>
