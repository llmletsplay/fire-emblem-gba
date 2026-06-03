import React from "react";
import type { Unit } from "../types/gameTypes";

interface InfoPanelProps {
  selectedUnit: Unit | null;
  enemyCount: number;
  allyCount: number;
}

const InfoPanel: React.FC<InfoPanelProps> = ({
  selectedUnit,
  enemyCount,
  allyCount,
}) => {
  return (
    <div className="info-panel">
      <h2>Unit Details</h2>

      {selectedUnit ? (
        <div className="unit-details">
          <h3>{selectedUnit.name}</h3>
          <p className="unit-class">{selectedUnit.unitClass}</p>

          <div className="stats-grid">
            <div className="stat-item">
              <span className="stat-name">Level</span>
              <span className="stat-value">{selectedUnit.level || 1}</span>
            </div>
            <div className="stat-item">
              <span className="stat-name">HP</span>
              <span className="stat-value">
                {selectedUnit.hp}/{selectedUnit.maxHp}
              </span>
            </div>
            <div className="stat-item">
              <span className="stat-name">Strength</span>
              <span className="stat-value">{selectedUnit.strength || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-name">Magic</span>
              <span className="stat-value">{selectedUnit.magic || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-name">Speed</span>
              <span className="stat-value">{selectedUnit.speed || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-name">Defense</span>
              <span className="stat-value">{selectedUnit.defense || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-name">Resistance</span>
              <span className="stat-value">{selectedUnit.resistance || 0}</span>
            </div>
            <div className="stat-item">
              <span className="stat-name">Movement</span>
              <span className="stat-value">{selectedUnit.movement || 0}</span>
            </div>
          </div>

          {selectedUnit.weapon && (
            <div className="weapon-info">
              <h4>Equipped</h4>
              <p>{selectedUnit.weapon}</p>
            </div>
          )}

          <div className="position-info">
            <h4>Position</h4>
            <p>
              X: {selectedUnit.x}, Y: {selectedUnit.y}
            </p>
          </div>
        </div>
      ) : (
        <div className="no-selection">
          <p>Select a unit to view details</p>
        </div>
      )}

      <div className="battlefield-summary">
        <h3>Battlefield</h3>
        <div className="summary-item">
          <span className="label">Enemy Units:</span>
          <span className="value">{enemyCount}</span>
        </div>
        <div className="summary-item">
          <span className="label">Allied Units:</span>
          <span className="value">{allyCount}</span>
        </div>
      </div>
    </div>
  );
};

export default InfoPanel;
