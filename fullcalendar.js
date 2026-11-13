import { loadResource } from "../../static/utils/resources.js";

// Copied from NiceGUI's examples/fullcalendar, with one change: the click event
// sends just the fixture id and title, instead of FullCalendar's whole event object.
export default {
  template: "<div></div>",
  emits: ["click"], // keep native clicks, e.g. on the toolbar buttons, from reaching the server
  props: {
    options: Array,
    resourcePath: String,
  },
  async mounted() {
    await this.$nextTick(); // wait for window.path_prefix to be set
    await loadResource(window.path_prefix + `${this.resourcePath}/index.global.min.js`);
    this.options.eventClick = (info) =>
      this.$emit("click", { id: info.event.id, title: info.event.title });
    this.calendar = new FullCalendar.Calendar(this.$el, this.options);
    this.calendar.render();
  },
  methods: {
    update_calendar() {
      if (this.calendar) {
        this.calendar.setOption("events", this.options.events);
        this.calendar.render();
      }
    },
  },
};