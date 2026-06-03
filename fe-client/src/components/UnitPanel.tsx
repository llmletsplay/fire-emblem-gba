import React from "react";
import type { Unit } from "../types/gameTypes";

interface UnitPanelProps {
  units: Unit[];
  selectedUnit: Unit | null;
  onSelectUnit: (unit: Unit) => void;
}

const UnitPanel: React.FC<UnitPanelProps> = ({
  units,
  selectedUnit,
  onSelectUnit,
}) => {
  return (
    <div className="unit-panel">
      <h2>Units</h2>
      <div className="unit-list">
        {units.map((unit) => (
          <div
            key={unit.id}
            className={`unit-item ${selectedUnit?.id === unit.id ? "selected" : ""}`}
            onClick={() => onSelectUnit(unit)}
          >
            <div className="unit-header">
              <span className="unit-name">{unit.name}</span>
              <span className="unit-class">{unit.unitClass}</span>
            </div>
            <div className="unit-stats">
              <div className="stat-bar">
                <span className="stat-label">HP</span>
                <div className="bar-container">
                  <div
                    className="bar-fill hp"
                    style={{ width: `${(unit.hp / unit.maxHp) * 100}%` }}
                  />
                  <span className="bar-text">
                    {unit.hp}/{unit.maxHp}
                  </span>
                </div>
              </div>
              {unit.exp !== undefined && (
                <div className="stat-bar">
                  <span className="stat-label">EXP</span>
                  <div className="bar-container">
                    <div
                      className="bar-fill exp"
                      style={{ width: `${unit.exp}%` }}
                    />
                    <span className="bar-text">{unit.exp}/100</span>
                  </div>
                </div>
              )}
            </div>
            <div className="unit-position">
              Position: ({unit.x}, {unit.y})
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default UnitPanel;
