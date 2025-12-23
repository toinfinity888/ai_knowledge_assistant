"""
Configuration API Routes
Provides REST endpoints for managing transcription configuration
"""
import logging
from flask import Blueprint, request, jsonify
from typing import Dict, Any

from app.config.transcription_config import (
    get_transcription_config,
    update_transcription_config,
    reset_transcription_config
)

logger = logging.getLogger(__name__)

config_bp = Blueprint('config', __name__, url_prefix='/api/config')


@config_bp.route('/transcription', methods=['GET'])
def get_config():
    """
    Get current transcription configuration

    Returns:
        JSON with current configuration values and parameter metadata
    """
    try:
        config = get_transcription_config()

        return jsonify({
            'success': True,
            'config': config.to_dict(),
            'parameters': config.get_parameter_info()
        }), 200

    except Exception as e:
        logger.error(f"Error getting config: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/transcription', methods=['POST'])
def update_config():
    """
    Update transcription configuration

    Request body:
        JSON object with configuration parameters to update

    Returns:
        JSON with updated configuration
    """
    try:
        updates = request.get_json()

        if not updates:
            return jsonify({
                'success': False,
                'error': 'No configuration updates provided'
            }), 400

        # Update configuration
        config = update_transcription_config(updates)

        logger.info(f"Configuration updated: {updates}")

        return jsonify({
            'success': True,
            'config': config.to_dict(),
            'updated_fields': list(updates.keys())
        }), 200

    except Exception as e:
        logger.error(f"Error updating config: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/transcription/reset', methods=['POST'])
def reset_config():
    """
    Reset transcription configuration to defaults

    Returns:
        JSON with default configuration
    """
    try:
        config = reset_transcription_config()

        logger.info("Configuration reset to defaults")

        return jsonify({
            'success': True,
            'config': config.to_dict(),
            'message': 'Configuration reset to defaults'
        }), 200

    except Exception as e:
        logger.error(f"Error resetting config: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@config_bp.route('/transcription/parameter/<parameter_name>', methods=['GET'])
def get_parameter_info(parameter_name: str):
    """
    Get metadata about a specific parameter

    Args:
        parameter_name: Name of the parameter

    Returns:
        JSON with parameter metadata
    """
    try:
        config = get_transcription_config()
        parameters = config.get_parameter_info()

        if parameter_name not in parameters:
            return jsonify({
                'success': False,
                'error': f'Unknown parameter: {parameter_name}'
            }), 404

        return jsonify({
            'success': True,
            'parameter': parameter_name,
            'info': parameters[parameter_name],
            'current_value': getattr(config, parameter_name)
        }), 200

    except Exception as e:
        logger.error(f"Error getting parameter info: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
