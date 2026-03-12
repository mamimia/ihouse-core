/**
 * Phase 376 — DMonogram Component
 *
 * The Domaniqo "D" monogram as a React component.
 * Single source of truth for the brand mark.
 * Used in: splash, navigation, footer, login, public pages.
 */

interface DMonogramProps {
    size?: number;
    color?: string;
    strokeWidth?: number;
    className?: string;
}

export default function DMonogram({
    size = 28,
    color = 'currentColor',
    strokeWidth = 2.2,
    className,
}: DMonogramProps) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 64 64"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={className}
            aria-label="Domaniqo"
            role="img"
        >
            <path
                d="M16 6H28C46 6 58 18 58 32C58 46 46 58 28 58H16Z"
                stroke={color}
                strokeWidth={strokeWidth}
                strokeLinejoin="round"
            />
            <line
                x1="28" y1="6" x2="28" y2="58"
                stroke={color}
                strokeWidth={strokeWidth * 0.55}
            />
            <line
                x1="16" y1="32" x2="52" y2="32"
                stroke={color}
                strokeWidth={strokeWidth * 0.55}
            />
            <path
                d="M28 13C40 13 51 22 51 32C51 42 40 51 28 51"
                stroke={color}
                strokeWidth={strokeWidth * 0.5}
                fill="none"
            />
        </svg>
    );
}
