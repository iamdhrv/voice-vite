# VoiceVite - Design Document

This document outlines the design inspirations, color palette, typography, and overall user experience (UX) goals for the VoiceVite project.

## 1. Design Inspiration

For a modern, clean, and trustworthy feel, we will take inspiration from:

*   **Source**: [Airtable's Website](https://www.airtable.com) and [Stripe's Website](https://stripe.com)
*   **Reasoning**: Both sites exhibit clarity, excellent use of whitespace, intuitive navigation, and a professional yet approachable aesthetic. They handle forms and data presentation effectively, which is relevant to VoiceVite's event detail input and RSVP tracking.

## 2. Color Palette

*   **Primary Color**: `#4A90E2` (Soothing Blue - for primary actions, links, and highlights)
*   **Secondary Color**: `#50E3C2` (Teal - for accents, success states, or secondary calls to action)
*   **Neutral Colors**:
    *   `#F8F9FA` (Light Gray - for backgrounds)
    *   `#FFFFFF` (White - for cards, content areas)
    *   `#343A40` (Dark Gray/Black - for text)
    *   `#6C757D` (Medium Gray - for secondary text, placeholders)
*   **Status Colors**:
    *   Success: `#28A745` (Green)
    *   Warning: `#FFC107` (Yellow)
    *   Error: `#DC3545` (Red)

## 3. Typography

*   **Primary Font**: 'Inter' (sans-serif) - Modern, highly legible, and versatile. Available via Google Fonts.
    *   Headings: `Inter Bold`
    *   Body Text: `Inter Regular`
    *   UI Elements (Buttons, Labels): `Inter Medium`
*   **Fallback Font**: `sans-serif`

## 4. Layout and Spacing

*   **Layout**: Clean, grid-based layout. Ample whitespace to reduce cognitive load.
*   **Spacing**: Consistent use of spacing units (e.g., multiples of 8px) for margins, padding, and component spacing.
*   **Responsiveness**: The design must be fully responsive, adapting gracefully to mobile, tablet, and desktop screens. Mobile-first approach where appropriate.

## 5. User Experience (UX) Principles

*   **Clarity**: Users should immediately understand what to do on each screen.
*   **Simplicity**: Minimize steps and complexity. The voice training, event creation, and guest upload processes should be straightforward.
*   **Efficiency**: Users should be able to complete tasks quickly.
*   **Feedback**: Provide clear feedback for user actions (e.g., form submission success/error, file upload progress).
*   **Accessibility (a11y)**:
    *   Sufficient color contrast.
    *   Keyboard navigability for all interactive elements.
    *   Use of ARIA attributes where necessary.
    *   Semantic HTML.

## 6. Key UI Components Style

*   **Buttons**: Rounded corners, clear call-to-action text. Primary buttons use the primary color, secondary buttons use a lighter shade or outline style.
*   **Forms**: Clearly labeled fields, inline validation messages, logical grouping of inputs.
*   **Cards**: Used for displaying event summaries or guest information, with subtle shadows for depth.
*   **Navigation**: Simple top navigation bar or sidebar if the application grows.

## 7. VoiceVite Specific UX Considerations

*   **Voice Training**: Clear instructions, progress indicator, and feedback on audio quality (if possible via ElevenLabs API).
*   **CSV Upload**: Clear template/instructions for CSV format, immediate feedback on successful upload or errors in the CSV.
*   **RSVP Display**: Easy-to-understand visualization of RSVP statuses.

This document will be updated as the design evolves. All frontend development should adhere to these guidelines to ensure a consistent and professional user interface.