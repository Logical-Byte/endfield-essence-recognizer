<template>
  <v-container>
    <h1>基质识别妙妙小工具</h1>

    <div class="d-flex flex-row flex-wrap ga-4">
      <v-btn
        append-icon="mdi-open-in-new"
        class="essence-btn"
        color="primary"
        href="https://cos.yituliu.cn/endfield/endfield-essence-recognizer/endfield-essence-recognizer-v0.2.1-windows.zip"
        rel="noopener"
        target="_blank"
        >下载最新版（国内）</v-btn
      >
      <v-btn
        append-icon="mdi-open-in-new"
        class="essence-btn"
        href="https://github.com/Logical-Byte/endfield-essence-recognizer/releases/latest"
        rel="noopener"
        target="_blank"
        >下载最新版（GitHub）</v-btn
      >
      <v-btn
        append-icon="mdi-open-in-new"
        class="essence-btn"
        href="https://github.com/Logical-Byte/endfield-essence-recognizer"
        rel="noopener"
        target="_blank"
        >项目地址</v-btn
      >
    </div>

    <section class="readme">
      <h2>使用前阅读</h2>
      <ul>
        <li>
          请使用<strong class="text-primary">管理员权限</strong
          ><span class="text-secondary">（是 Windows 管理员，不是终末地管理员）</span
          >运行本工具，否则无法捕获全局热键
        </li>
        <li>
          请在终末地的设置中将分辨率调整为 <strong class="text-primary">1920×1080 窗口</strong>
        </li>
        <li>
          请按 <v-hotkey keys="K" inline variant="flat" /> 键打开终末地<strong class="text-primary"
            >贵重品库</strong
          >并切换到<strong class="text-primary">武器基质</strong>页面
        </li>
        <li>在运行过程中，请确保终末地窗口<strong class="text-primary">置于前台</strong></li>
      </ul>

      <h2>功能介绍</h2>
      <ul>
        <li>按 <v-hotkey keys="[" inline variant="flat" /> 键识别当前选中的基质是宝藏还是垃圾</li>
        <li>
          按
          <v-hotkey keys="]" inline variant="flat" />
          键扫描所有基质，并根据<router-link
            to="/settings"
            class="text-primary text-decoration-none"
            ><strong>设置</strong></router-link
          >，自动锁定或者解锁基质<br />
          基质扫描过程中再次按 <v-hotkey keys="]" inline variant="flat" /> 键中断扫描
        </li>

        <li>按 <v-hotkey keys="Alt+DELETE" inline variant="flat" /> 退出程序</li>
      </ul>

      <p>
        <strong class="text-primary">宝藏基质和垃圾基质：</strong>可以在<router-link
          to="/settings"
          class="text-primary text-decoration-none"
          ><strong>设置</strong></router-link
        >界面自定义。默认情况下，如果这个基质和任何一把武器能对上<span class="text-secondary"
          >（基质的所有属性与至少 1 件已实装武器的属性完全相同）</span
        >，则是宝藏，否则是垃圾。
      </p>

      <h2>说明</h2>
      <ul>
        <li>机器识别，可能存在错误。若发现错误，欢迎反馈。</li>
        <li>
          工具仅检索基质是否匹配已实装的武器，而没有能力预测是否能匹配未实装的武器。至于一个基质未来有没有用，你可以给海猫打个电话（
        </li>
        <li>“宝藏”和“垃圾”仅为分类简称，不代表价值判断或其他含义。</li>
        <li>本工具按“原样”提供，作者不对可用性、准确性或使用效果作出任何保证。</li>
        <li>使用者必须确保使用本工具符合相关法律法规与服务条款，禁止用于任何违法或侵权行为。</li>
        <li>使用者需承担因使用本工具产生的任何风险、损失或责任。</li>
        <li>使用本工具即意味着您同意以上全部内容。</li>
      </ul>
    </section>
  </v-container>
</template>

<script lang="ts" setup></script>

<style scoped lang="scss"></style>
