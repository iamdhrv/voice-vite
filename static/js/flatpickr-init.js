// Flatpickr initialization for all date and time pickers
// Requires flatpickr to be loaded via CDN in the template

document.addEventListener('DOMContentLoaded', function() {
  // Date pickers
  document.querySelectorAll('input[type="date"], .datepicker').forEach(function(el) {
    flatpickr(el, {
      dateFormat: 'Y-m-d',
      allowInput: true,
      altInput: true,
      altFormat: 'F j, Y',
      theme: 'airbnb', // We'll override with ShadCN variables in CSS
    });
  });
  // Time pickers
  document.querySelectorAll('input[type="time"], .timepicker').forEach(function(el) {
    flatpickr(el, {
      enableTime: true,
      noCalendar: true,
      dateFormat: 'H:i',
      time_24hr: false,
      allowInput: true,
      theme: 'airbnb',
    });
  });
  // DateTime picker for event_datetime
  document.querySelectorAll('input#event_datetime, .datetimepicker').forEach(function(el) {
    flatpickr(el, {
      enableTime: true,
      dateFormat: 'Y-m-d H:i',
      altInput: true,
      altFormat: 'F j, Y h:i K',
      allowInput: true,
      time_24hr: false,
      theme: 'airbnb',
    });
  });
});
