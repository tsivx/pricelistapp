import type { ComponentCustomProperties } from 'vue'
declare module 'vue' {
  interface ComponentCustomProperties {}
}
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}
